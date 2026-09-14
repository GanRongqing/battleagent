"""UAV 最小真实树 — COOPERATIVE_LOCK / SITUATION_UPDATE / RETURN_RECHARGE /
HOLD_POSITION

  root（Selector 非 memory）
    ├─ safety_hold（REJECTED/OVERRIDDEN → 悬停）
    ├─ cooperative_lock → Sequence(approach → orbit)（docked 先 LAUNCH）
    ├─ situation_update → navigate（飞往航点；docked 先 LAUNCH；到达即完成）
    ├─ return_recharge → Sequence(return → dock)：返航至母舰 5km 内 → 先减速
    │                   至降落速度（引擎要求 speed<100）→ land_uav → 完成
    └─ hold_fallback（悬停）
"""

from typing import Dict, Optional

from .harness_interface import (
    ActionKind, FeedbackReason, Phase, PlatformType, TaskType)
from .base import Behavior, BehaviorTree, Node, Selector, Sequence
from .blackboard import Blackboard
from .helpers import (_bearing, _dist, _emit, _own, _own_course, _param,
                      _target_track, hold_fn, safety_hold_fn, task_type_is)
from .status import (GOTO_RANGE_M, LAND_RANGE_M, STANDOFF_DEFAULT_M, Status,
                     UAV_CRUISE_SPEED, UAV_LAND_APPROACH_SPEED,
                     UAV_TAKEOFF_COURSE)


def _uav_base_name(bb: Blackboard) -> str:
    """母舰名：约束 base 优先，其次平台状态记忆（飞行中引擎 home_name 为空）"""
    constraints = bb.get("task.constraints") or {}
    base = constraints.get("base")
    if base:
        return str(base)
    state = bb.get("ctx.platform_state") or {}
    return state.get("home_name") or bb.get("uav.home") or ""


def _uav_base_track(bb: Blackboard) -> Optional[Dict]:
    """母舰位置：从 tracks 中 is_ship=True 的友方舰船查"""
    base = _uav_base_name(bb)
    if not base:
        return None
    tracks = bb.get("ctx.tracks") or {}
    return tracks.get(base)


def _uav_launch_if_docked(bb: Blackboard) -> Status:
    """在舰上（is_at_usv）→ 先 LAUNCH，起飞后再飞"""
    state = bb.get("ctx.platform_state") or {}
    if state.get("is_at_usv"):
        _emit(bb, ActionKind.LAUNCH,
              meta={"home": _uav_base_name(bb)},
              speed=_param(bb, "cruise_speed", UAV_CRUISE_SPEED),
              course=_param(bb, "takeoff_course", UAV_TAKEOFF_COURSE),
              phase=Phase.dock, branch="launch")
        return Status.RUNNING
    return Status.SUCCESS


def _uav_approach(bb: Blackboard) -> Status:
    """cooperative_lock：接近目标至 standoff 圈"""
    tr = _target_track(bb)
    if tr is None:
        bb.set("reason", FeedbackReason.target_lost)
        return Status.FAILURE
    own = _own(bb)
    tpos = tr.get("position")
    standoff = _param(bb, "standoff_distance", STANDOFF_DEFAULT_M)
    if _dist(own, tpos) <= standoff:
        return Status.SUCCESS
    _emit(bb, ActionKind.APPROACH_TARGET, target_id=bb.get("task.target_id"),
          course=_bearing(own, tpos),
          speed=_param(bb, "cruise_speed", UAV_CRUISE_SPEED),
          phase=Phase.approach, branch="approach")
    return Status.RUNNING


def _uav_orbit(bb: Blackboard) -> Status:
    """传感器 standoff 环绕（目标移动时圆跟着走）"""
    tr = _target_track(bb)
    if tr is None:
        bb.set("reason", FeedbackReason.target_lost)
        return Status.FAILURE
    own = _own(bb)
    tpos = tr.get("position")
    b = _bearing(own, tpos)
    d = _dist(own, tpos)
    standoff = _param(bb, "standoff_distance", STANDOFF_DEFAULT_M)
    if d < standoff * 0.8:
        course = (b + 180) % 360
    elif d > standoff * 1.2:
        course = b
    else:
        course = (b + 90) % 360
    _emit(bb, ActionKind.ORBIT_TARGET, target_id=bb.get("task.target_id"),
          course=course,
          speed=_param(bb, "orbit_speed", UAV_CRUISE_SPEED),
          phase=Phase.orbit, branch="orbit")
    return Status.RUNNING


def _uav_navigate(bb: Blackboard) -> Status:
    """situation_update：飞往航点（constraints.waypoint）；到达 → 任务完成"""
    constraints = bb.get("task.constraints") or {}
    wp = constraints.get("waypoint")
    if not wp:
        return Status.FAILURE
    own = _own(bb)
    if _dist(own, wp) <= GOTO_RANGE_M:
        bb.set("task.completed", True)
        bb.set("reason", FeedbackReason.task_completed)
        return Status.SUCCESS
    _emit(bb, ActionKind.NAVIGATE_TO, waypoint=(float(wp[0]), float(wp[1])),
          course=_bearing(own, wp),
          speed=_param(bb, "cruise_speed", UAV_CRUISE_SPEED),
          phase=Phase.search, branch="navigate")
    return Status.RUNNING


def _uav_docked_done(bb: Blackboard) -> Status:
    """return_recharge：已停靠 → 任务完成（充电）"""
    state = bb.get("ctx.platform_state") or {}
    if state.get("is_at_usv"):
        bb.set("task.completed", True)
        bb.set("reason", FeedbackReason.task_completed)
        return Status.SUCCESS
    return Status.FAILURE


def _uav_return(bb: Blackboard) -> Status:
    """返航：飞向母舰；5km 内 → SUCCESS（转降落）"""
    tr = _uav_base_track(bb)
    if tr is None:
        bb.set("reason", FeedbackReason.unreachable)
        return Status.FAILURE
    own = _own(bb)
    bpos = tr.get("position")
    if _dist(own, bpos) <= LAND_RANGE_M:
        return Status.SUCCESS
    _emit(bb, ActionKind.RETURN_TO_BASE,
          meta={"base": _uav_base_name(bb)},
          course=_bearing(own, bpos),
          speed=_param(bb, "cruise_speed", UAV_CRUISE_SPEED),
          phase=Phase.return_, branch="return")
    return Status.RUNNING


def _uav_dock(bb: Blackboard) -> Status:
    """降落：先减速至降落速度，再显式 land_uav；停靠成功后下一 tick
    由 docked_done 判完成。

    减速门槛取降落速度而非 100：引擎降落要求 speed<100，而仿真持续
    运行、采样速度滞后于指令执行时刻（正加速向巡航速度的 UAV 采样
    可能 <100，指令到达时已 >=100 被拒）。降至 60 后执行 land 时
    速度稳定 <100。"""
    state = bb.get("ctx.platform_state") or {}
    if state.get("is_at_usv"):
        bb.set("task.completed", True)
        bb.set("reason", FeedbackReason.task_completed)
        return Status.SUCCESS
    if float(state.get("speed", 0) or 0) > UAV_LAND_APPROACH_SPEED:
        # 先减速航段（朝母舰，目标降至降落速度）
        tr = _uav_base_track(bb)
        _emit(bb, ActionKind.RETURN_TO_BASE,
              meta={"base": _uav_base_name(bb)},
              course=_bearing(_own(bb), tr.get("position"))
              if tr else _own_course(bb),
              speed=UAV_LAND_APPROACH_SPEED, phase=Phase.dock, branch="dock")
        return Status.RUNNING
    _emit(bb, ActionKind.LAND_OR_DOCK, meta={"base": _uav_base_name(bb)},
          phase=Phase.dock, branch="dock")
    return Status.RUNNING


def _uav_root() -> Node:
    return Selector("root", [
        Behavior("safety_hold", lambda bb: safety_hold_fn(bb, uav=True)),
        Selector("task", [
            Sequence("hold_position", [
                Behavior("type_hold", lambda bb: task_type_is(bb, TaskType.HOLD_POSITION)),
                Behavior("hover", lambda bb: hold_fn(bb, uav=True)),
            ]),
            Sequence("cooperative_lock", [
                Behavior("type_coop", lambda bb: task_type_is(bb, TaskType.COOPERATIVE_LOCK)),
                Behavior("launch_if_docked", _uav_launch_if_docked),
                Behavior("approach", _uav_approach),
                Behavior("orbit", _uav_orbit),
            ]),
            Sequence("situation_update", [
                Behavior("type_sit", lambda bb: task_type_is(bb, TaskType.SITUATION_UPDATE)),
                Behavior("launch_if_docked", _uav_launch_if_docked),
                Behavior("navigate", _uav_navigate),
            ]),
            Selector("return_recharge", [
                Sequence("docked_done", [
                    Behavior("type_return", lambda bb: task_type_is(bb, TaskType.RETURN_RECHARGE)),
                    Behavior("docked", _uav_docked_done),
                ]),
                Sequence("return_dock", [
                    Behavior("type_return", lambda bb: task_type_is(bb, TaskType.RETURN_RECHARGE)),
                    Behavior("return_home", _uav_return),
                    Behavior("dock", _uav_dock),
                ]),
            ]),
        ]),
        Behavior("hold_fallback", lambda bb: hold_fn(bb, uav=True)),
    ], memory=False)


def build_uav_tree(platform_id: str) -> BehaviorTree:
    """UAV 最小真实树（COOPERATIVE_LOCK / SITUATION_UPDATE /
    RETURN_RECHARGE / HOLD_POSITION）"""
    bb = Blackboard()
    bb.set("platform_id", platform_id)
    bb.set("platform_type", PlatformType.UAV)
    return BehaviorTree(_uav_root(), bb)
