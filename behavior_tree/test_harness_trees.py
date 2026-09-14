"""真实树验证 — §5 tick 语义（USV / UAV / safety / target 不可变）

运行: python3 -m unittest behavior_tree.test_harness_trees -v
（纯标准库，不需要仿真后端）
"""

import unittest

from behavior_tree.harness_interface import (
    ActionKind, ExecutionContext, FeedbackReason, PlatformType, TaskStatus,
    TaskType)
from behavior_tree.bt_bridge import BTBridge
from behavior_tree.usv_bt import build_usv_tree
from behavior_tree.uav_bt import build_uav_tree


def _step(tree, sim_time, platform_state, tracks, safety=None):
    """完整一步: pre_tick → tree.tick → post_tick（与端口驱动一致）"""
    ctx = ExecutionContext(platform_id=tree.blackboard.get("platform_id"),
                           platform_type=tree.blackboard.get("platform_type"),
                           sim_time=sim_time,
                           platform_state=platform_state, tracks=tracks,
                           safety_feedback=safety)
    BTBridge.pre_tick(tree, ctx)
    status = tree.tick()
    return ctx, BTBridge.post_tick(tree, ctx, status)


def _kinds(result):
    return [a.action_kind for a in result.action_requests]


class USVTreeTest(unittest.TestCase):
    def setUp(self):
        self.tree = build_usv_tree("white_usv1")
        bb = self.tree.blackboard
        bb.set("task.task_id", "t1")
        bb.set("task.task_type", TaskType.INTERCEPT_LOCK)
        bb.set("task.target_id", "enemy_3")
        bb.set("task.constraints", {})
        bb.set("task.allow_local_reacquire", True)
        bb.set("task.max_search_time", 60.0)
        bb.set("task.status", TaskStatus.RUNNING)
        self.state = {"position": [0, 0, 0], "heading": 0, "is_alive": True,
                      "is_locking": False, "locking_unit": ""}
        self.far = {"enemy_3": {"position": [50000, 0, 0], "visible": True,
                                "confidence": 1.0, "is_ship": False}}
        self.near = {"enemy_3": {"position": [10000, 0, 0], "visible": True,
                                 "confidence": 1.0, "is_ship": False}}

    def test_far_approach(self):
        _, res = _step(self.tree, 100, self.state, self.far)
        self.assertIn(ActionKind.APPROACH_TARGET, _kinds(res))
        self.assertEqual(res.root_status, "RUNNING")
        self.assertEqual(res.task_feedback.phase, "approach")

    def test_in_range_lock_once_then_orbit(self):
        # 进锁距：同一 tick 发一次 ENGAGE(lock) + ORBIT(standoff)
        _, res = _step(self.tree, 100, self.state, self.near)
        kinds = _kinds(res)
        self.assertIn(ActionKind.ENGAGE_TARGET, kinds)
        self.assertIn(ActionKind.ORBIT_TARGET, kinds)
        # 通道约束：WEAPON + NAVIGATION 各至多 1 个
        channels = [a.channel for a in res.action_requests]
        self.assertEqual(len(channels), len(set(channels)))
        # 下一 tick 不再重复 lock（保护 300s 锁链），只发 standoff
        _, res2 = _step(self.tree, 130, self.state, self.near)
        self.assertNotIn(ActionKind.ENGAGE_TARGET, _kinds(res2))
        self.assertIn(ActionKind.ORBIT_TARGET, _kinds(res2))

    def test_already_locking_no_relock(self):
        state = dict(self.state, is_locking=True, locking_unit="enemy_3")
        _, res = _step(self.tree, 100, state, self.near)
        self.assertNotIn(ActionKind.ENGAGE_TARGET, _kinds(res))
        self.assertIn(ActionKind.ORBIT_TARGET, _kinds(res))

    def test_lost_reacquire_and_timeout(self):
        # 目标丢失 → REACQUIRE（SENSOR 通道）
        _, res = _step(self.tree, 100, self.state, {})
        self.assertIn(ActionKind.REACQUIRE, _kinds(res))
        self.assertEqual(res.task_feedback.reason_code,
                         FeedbackReason.target_lost)
        self.assertEqual(res.task_feedback.phase, "reacquire")
        # 超时（60s）→ need_reallocation，无动作
        _, res2 = _step(self.tree, 200, self.state, {})
        self.assertEqual(res2.action_requests, [])
        self.assertTrue(res2.task_feedback.need_reallocation)
        self.assertEqual(res2.task_feedback.reason_code,
                         FeedbackReason.target_lost_timeout)

    def test_reacquire_blocked(self):
        self.tree.blackboard.set("task.allow_local_reacquire", False)
        _, res = _step(self.tree, 100, self.state, {})
        self.assertEqual(res.action_requests, [])
        self.assertTrue(res.task_feedback.need_reallocation)
        self.assertEqual(res.task_feedback.reason_code, FeedbackReason.blocked)

    def test_hold_position_and_no_target(self):
        bb = self.tree.blackboard
        bb.set("task.task_type", TaskType.HOLD_POSITION)
        bb.set("task.target_id", None)
        _, res = _step(self.tree, 100, self.state, {})
        self.assertEqual(_kinds(res), [ActionKind.HOLD])
        self.assertEqual(res.task_feedback.phase, "hold")

    def test_safety_hold_and_clamped(self):
        safety = {"white_usv1 移动 target_speed=20 target_course=90.0":
                  "REJECTED"}
        _, res = _step(self.tree, 100, self.state, self.far, safety=safety)
        self.assertEqual(_kinds(res), [ActionKind.HOLD])
        self.assertEqual(res.task_feedback.reason_code,
                         FeedbackReason.safety_rejected)
        # CLAMPED/MODIFIED 不误判失败，继续可行分支
        safety = {"white_usv1 移动 target_speed=20 target_course=90.0":
                  "CLAMPED"}
        _, res2 = _step(self.tree, 130, self.state, self.far, safety=safety)
        self.assertIn(ActionKind.APPROACH_TARGET, _kinds(res2))

    def test_target_immutable(self):
        # 环境里更近的 enemy_4 不会改变锁定对象（树内无 allocator）
        tracks = dict(self.far)
        tracks["enemy_4"] = {"position": [1000, 0, 0], "visible": True,
                             "confidence": 1.0, "is_ship": False}
        _, res = _step(self.tree, 100, self.state, tracks)
        self.assertEqual(res.task_feedback.target_id, "enemy_3")
        for a in res.action_requests:
            self.assertEqual(a.target_id, "enemy_3")

    def test_no_ground_truth_keys(self):
        # 树只读合法上下文：tracks 中即使混入真值字段也不应被引用
        tracks = {"enemy_3": {"position": [50000, 0, 0], "visible": True,
                              "confidence": 1.0, "is_ship": False,
                              "ground_truth": {"x": 1, "y": 2}}}
        _, res = _step(self.tree, 100, self.state, tracks)
        self.assertIn(ActionKind.APPROACH_TARGET, _kinds(res))


class UAVTreeTest(unittest.TestCase):
    def setUp(self):
        self.tree = build_uav_tree("white_uav1")
        bb = self.tree.blackboard
        bb.set("task.task_id", "t2")
        bb.set("task.task_type", TaskType.SITUATION_UPDATE)
        bb.set("task.target_id", None)
        bb.set("task.constraints", {"waypoint": [50000, 0]})
        bb.set("task.allow_local_reacquire", True)
        bb.set("task.max_search_time", 60.0)
        bb.set("task.status", TaskStatus.RUNNING)
        self.base_track = {"white_usv1": {"position": [0, 0, 0],
                                          "visible": True, "confidence": 1.0,
                                          "is_ship": True}}

    def _state(self, **kw):
        s = {"position": [0, 0, 0], "heading": 0, "is_alive": True,
             "is_at_usv": False, "home_name": "white_usv1"}
        s.update(kw)
        return s

    def test_launch_if_docked(self):
        _, res = _step(self.tree, 100,
                       self._state(is_at_usv=True), self.base_track)
        self.assertEqual(_kinds(res), [ActionKind.LAUNCH])
        self.assertEqual(res.task_feedback.phase, "dock")

    def test_navigate_then_complete(self):
        # 起飞后：飞往航点
        _, res = _step(self.tree, 130,
                       self._state(position=[20000, 0, 0]), self.base_track)
        self.assertIn(ActionKind.NAVIGATE_TO, _kinds(res))
        self.assertEqual(res.task_feedback.phase, "search")
        # 到达航点（10km 内）→ 根 SUCCESS（执行器侧 → COMPLETED）
        _, res2 = _step(self.tree, 160,
                        self._state(position=[45000, 0, 0]), self.base_track)
        self.assertEqual(res2.root_status, "SUCCESS")
        self.assertTrue(self.tree.blackboard.get("task.completed"))

    def test_cooperative_lock_approach_then_orbit(self):
        bb = self.tree.blackboard
        bb.set("task.task_type", TaskType.COOPERATIVE_LOCK)
        bb.set("task.target_id", "enemy_3")
        tracks = dict(self.base_track)
        tracks["enemy_3"] = {"position": [50000, 0, 0], "visible": True,
                             "confidence": 1.0, "is_ship": False}
        # 50km > standoff(35km) → 接近
        _, res = _step(self.tree, 100,
                       self._state(position=[0, 0, 0]), tracks)
        self.assertIn(ActionKind.APPROACH_TARGET, _kinds(res))
        self.assertEqual(res.task_feedback.phase, "approach")
        # 进入 standoff（30km）→ 环绕
        _, res2 = _step(self.tree, 130,
                        self._state(position=[20000, 0, 0]), tracks)
        self.assertIn(ActionKind.ORBIT_TARGET, _kinds(res2))
        self.assertEqual(res2.task_feedback.phase, "orbit")

    def test_return_dock_complete(self):
        bb = self.tree.blackboard
        bb.set("task.task_type", TaskType.RETURN_RECHARGE)
        bb.set("task.target_id", None)
        # 远离母舰 → 返航
        _, res = _step(self.tree, 100,
                       self._state(position=[20000, 0, 0]), self.base_track)
        self.assertIn(ActionKind.RETURN_TO_BASE, _kinds(res))
        self.assertEqual(res.task_feedback.phase, "return")
        # 5km 内 → 降落
        _, res2 = _step(self.tree, 130,
                        self._state(position=[3000, 0, 0]), self.base_track)
        self.assertIn(ActionKind.LAND_OR_DOCK, _kinds(res2))
        self.assertEqual(res2.task_feedback.phase, "dock")
        # 已停靠 → 完成
        _, res3 = _step(self.tree, 160,
                        self._state(position=[0, 0, 0], is_at_usv=True),
                        self.base_track)
        self.assertEqual(res3.root_status, "SUCCESS")
        self.assertTrue(self.tree.blackboard.get("task.completed"))

    def test_uav_safety_hold_hover(self):
        safety = {"white_uav1 飞行 target_speed=100 target_course=90.0":
                  "OVERRIDDEN"}
        _, res = _step(self.tree, 100,
                       self._state(position=[20000, 0, 0]),
                       self.base_track, safety=safety)
        self.assertEqual(_kinds(res), [ActionKind.HOLD])
        self.assertEqual(res.task_feedback.reason_code,
                         FeedbackReason.safety_override)
        # 悬停速度 0（固定翼无 Hover 模式，速度 0 飞行即原地盘旋）
        self.assertEqual(res.action_requests[0].speed, 0.0)


if __name__ == "__main__":
    unittest.main()
