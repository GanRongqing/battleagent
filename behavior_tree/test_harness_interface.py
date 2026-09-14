"""harness_interface 接口测试 — §4 生命周期语义 / tick 时效 / §6 适配器

运行: python3 -m unittest behavior_tree.test_harness_interface -v
（纯标准库，不需要仿真后端）
"""

import unittest

from behavior_tree.harness_interface import (
    ACTION_CHANNEL, AckCode, ActionChannel, ActionKind, BTActionAdapter,
    BTPlatformExecutive, CancelTaskRequest, ExecutionContext, FeedbackReason,
    PlatformType, TaskCommand, TaskType)


def _cmd(platform_id="white_usv1", platform_type=PlatformType.USV,
         task_id="t1", task_type=TaskType.INTERCEPT_LOCK,
         target_id="enemy_3", **kw) -> TaskCommand:
    return TaskCommand(task_id=task_id, platform_id=platform_id,
                       platform_type=platform_type, task_type=task_type,
                       target_id=target_id, **kw)


def _ctx(sim_time=100.0, platform_id="white_usv1",
         platform_type=PlatformType.USV, **kw) -> ExecutionContext:
    return ExecutionContext(platform_id=platform_id,
                            platform_type=platform_type, sim_time=sim_time, **kw)


class SubmitLifecycleTest(unittest.TestCase):
    """§4 submit_task 判定顺序"""

    def setUp(self):
        self.ex = BTPlatformExecutive("white_usv1", PlatformType.USV)

    def test_accept_new_task(self):
        ack = self.ex.submit_task(_cmd())
        self.assertEqual(ack.code, AckCode.ACCEPTED)
        self.assertIsNotNone(self.ex.active_task)

    def test_invalid_platform_and_type(self):
        ack = self.ex.submit_task(_cmd(platform_id="white_usv2"))
        self.assertEqual(ack.code, AckCode.INVALID_PLATFORM)
        ack = self.ex.submit_task(_cmd(platform_type=PlatformType.UAV))
        self.assertEqual(ack.code, AckCode.INVALID_TYPE)

    def test_expired_before_accept(self):
        cmd = _cmd(valid_until=50.0)
        ack = self.ex.submit_task(cmd, now_sim=100.0)
        self.assertEqual(ack.code, AckCode.EXPIRED)

    def test_duplicate_ignored(self):
        self.ex.submit_task(_cmd())
        ack = self.ex.submit_task(_cmd())     # 同 task_id + 同 revision
        self.assertEqual(ack.code, AckCode.DUPLICATE_IGNORED)

    def test_stale_and_update_revision(self):
        self.ex.submit_task(_cmd())
        ack = self.ex.submit_task(_cmd(revision=0))
        self.assertEqual(ack.code, AckCode.STALE_REJECTED)
        ack = self.ex.submit_task(_cmd(revision=2))
        self.assertEqual(ack.code, AckCode.ACCEPTED)   # 更新接受
        self.assertEqual(self.ex.active_task.revision, 2)

    def test_stale_plan_revision(self):
        self.ex.submit_task(_cmd(plan_id="p1", plan_revision=3))
        ack = self.ex.submit_task(_cmd(task_id="t2", plan_id="p1",
                                       plan_revision=2))
        self.assertEqual(ack.code, AckCode.STALE_REJECTED)

    def test_preemption_rules(self):
        # 旧任务 preemptible → 普通抢占
        self.ex.submit_task(_cmd(task_id="t1", preemptible=True))
        ack = self.ex.submit_task(_cmd(task_id="t2"))
        self.assertEqual(ack.code, AckCode.ACCEPTED_WITH_PREEMPTION)
        self.assertEqual(self.ex.active_task.task_id, "t2")

        # 不可抢占 + 低优先级 → BUSY
        self.ex.submit_task(_cmd(task_id="t3", preemptible=False, priority=10))
        ack = self.ex.submit_task(_cmd(task_id="t4", priority=5))
        self.assertEqual(ack.code, AckCode.BUSY)

        # 高优先级可抢占不可抢占任务
        ack = self.ex.submit_task(_cmd(task_id="t5", priority=20))
        self.assertEqual(ack.code, AckCode.ACCEPTED_WITH_PREEMPTION)

        # safety_override 可抢占任何任务（含非可抢占）
        self.ex.submit_task(_cmd(task_id="t6", preemptible=False, priority=99))
        ack = self.ex.submit_task(_cmd(task_id="t7", priority=0,
                                       safety_override=True))
        self.assertEqual(ack.code, AckCode.ACCEPTED_WITH_PREEMPTION)


class CancelTest(unittest.TestCase):
    def test_cancel_and_not_found(self):
        ex = BTPlatformExecutive("white_usv1", PlatformType.USV)
        ex.submit_task(_cmd())
        ack = ex.cancel_task(CancelTaskRequest(platform_id="white_usv1",
                                               task_id="t1"))
        self.assertEqual(ack.code, AckCode.CANCELLED)
        self.assertIsNone(ex.active_task)
        # 再取消 → NOT_FOUND
        ack = ex.cancel_task(CancelTaskRequest(platform_id="white_usv1",
                                               task_id="t1"))
        self.assertEqual(ack.code, AckCode.NOT_FOUND)
        # 平台不匹配 → NOT_FOUND
        ack = ex.cancel_task(CancelTaskRequest(platform_id="white_usv2",
                                               task_id="t1"))
        self.assertEqual(ack.code, AckCode.NOT_FOUND)


class TickGuardTest(unittest.TestCase):
    """tick 时效与空转语义"""

    def test_idle_without_task(self):
        ex = BTPlatformExecutive("white_usv1", PlatformType.USV)
        res = ex.tick(_ctx())
        self.assertEqual(res.root_status, "IDLE")
        self.assertEqual(res.action_requests, [])

    def test_not_yet_valid(self):
        ex = BTPlatformExecutive("white_usv1", PlatformType.USV)
        ex.submit_task(_cmd(valid_from=200.0))
        res = ex.tick(_ctx(sim_time=100.0))
        self.assertEqual(res.root_status, "IDLE")
        self.assertEqual(res.action_requests, [])
        self.assertEqual(res.task_feedback.reason_code,
                         FeedbackReason.not_yet_valid)

    def test_expired_at_tick(self):
        ex = BTPlatformExecutive("white_usv1", PlatformType.USV)
        ex.submit_task(_cmd(valid_until=150.0))
        res = ex.tick(_ctx(sim_time=200.0))
        self.assertEqual(res.root_status, "IDLE")
        self.assertEqual(res.action_requests, [])
        self.assertTrue(res.task_feedback.need_reallocation)
        self.assertEqual(res.task_feedback.reason_code,
                         FeedbackReason.expired)

    def test_running_with_target(self):
        ex = BTPlatformExecutive("white_usv1", PlatformType.USV)
        ex.submit_task(_cmd())
        res = ex.tick(_ctx(
            platform_state={"position": [0, 0, 0], "heading": 0,
                            "is_alive": True, "is_locking": False},
            tracks={"enemy_3": {"position": [50000, 0, 0], "visible": True,
                                "confidence": 1.0, "is_ship": False}}))
        self.assertEqual(res.root_status, "RUNNING")
        self.assertGreaterEqual(len(res.action_requests), 1)
        self.assertEqual(res.task_feedback.task_id, "t1")
        self.assertEqual(res.task_feedback.target_id, "enemy_3")
        self.assertTrue(res.task_feedback.target_visible)


class AdapterTest(unittest.TestCase):
    """§6 BTActionAdapter 映射表"""

    def test_adapter_mapping(self):
        adapter = BTActionAdapter()

        def item(kind, platform_id="white_usv1", **kw):
            from behavior_tree.harness_interface import ActionRequest
            return adapter.to_action_item(
                ActionRequest(platform_id=platform_id, action_kind=kind, **kw))

        # ENGAGE → 锁定
        self.assertEqual(item(ActionKind.ENGAGE_TARGET,
                              target_id="enemy_3"),
                         {"action_text": "white_usv1 锁定 enemy_3",
                          "action_type": "lock"})
        # 导航类（USV）→ 移动
        self.assertEqual(
            item(ActionKind.APPROACH_TARGET, course=92.6, speed=20.0),
            {"action_text":
             "white_usv1 移动 target_speed=20 target_course=92.6",
             "action_type": "move"})
        # 导航类（UAV）→ 飞行（数值格式：整数不带小数点，与 /apply 解析约定一致）
        self.assertEqual(
            item(ActionKind.ORBIT_TARGET, platform_id="white_uav1",
                 course=45.0, speed=100.0),
            {"action_text":
             "white_uav1 飞行 target_speed=100 target_course=45",
             "action_type": "fly"})
        # LAUNCH → 起飞
        self.assertEqual(
            item(ActionKind.LAUNCH, platform_id="white_uav1",
                 meta={"home": "white_usv1"}, speed=100.0, course=90.0),
            {"action_text":
             "white_uav1 从 white_usv1 起飞 target_speed=100 target_course=90",
             "action_type": "launch_uav"})
        # LAND → 降落
        self.assertEqual(
            item(ActionKind.LAND_OR_DOCK, platform_id="white_uav1",
                 meta={"base": "white_usv1"}),
            {"action_text": "white_uav1 降落到 white_usv1",
             "action_type": "land_uav"})
        # HOLD → 移动
        self.assertEqual(
            item(ActionKind.HOLD, course=90.0, speed=20.0),
            {"action_text":
             "white_usv1 移动 target_speed=20 target_course=90",
             "action_type": "move"})

    def test_no_preset_values(self):
        """无预设策略数值：数值缺失的动作不产出（返回 None）"""
        adapter = BTActionAdapter()

        def item(kind, platform_id="white_usv1", **kw):
            from behavior_tree.harness_interface import ActionRequest
            return adapter.to_action_item(
                ActionRequest(platform_id=platform_id, action_kind=kind, **kw))

        # 导航类缺速度/航向 → 不产出
        self.assertIsNone(item(ActionKind.APPROACH_TARGET, course=92.6))
        self.assertIsNone(item(ActionKind.HOLD))
        # 起飞缺母舰或数值 → 不产出
        self.assertIsNone(item(ActionKind.LAUNCH, platform_id="white_uav1"))
        # 降落缺母舰 → 不产出
        self.assertIsNone(item(ActionKind.LAND_OR_DOCK,
                               platform_id="white_uav1"))

    def test_channel_mapping(self):
        self.assertEqual(ACTION_CHANNEL[ActionKind.NAVIGATE_TO],
                         ActionChannel.NAVIGATION)
        self.assertEqual(ACTION_CHANNEL[ActionKind.REACQUIRE],
                         ActionChannel.SENSOR)
        self.assertEqual(ACTION_CHANNEL[ActionKind.ENGAGE_TARGET],
                         ActionChannel.WEAPON)
        self.assertEqual(ACTION_CHANNEL[ActionKind.HOLD],
                         ActionChannel.NAVIGATION)
        self.assertEqual(ACTION_CHANNEL[ActionKind.LAUNCH],
                         ActionChannel.NAVIGATION)


if __name__ == "__main__":
    unittest.main()
