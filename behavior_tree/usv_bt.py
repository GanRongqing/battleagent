"""USV 最小真实树 — INTERCEPT_LOCK / ENGAGE_TARGET / HOLD_POSITION

  root（Selector 非 memory）
    ├─ safety_hold（REJECTED/OVERRIDDEN → HOLD）
    ├─ 无目标/HOLD_POSITION → hold
    ├─ visible → Sequence(approach → engage)：远离→approach；进锁距→
    │           先发一次 ENGAGE(lock) 再 ORBIT standoff move；
    │           已锁定/已发过不再重复 lock（保护 300s 锁链）
    ├─ lost → reacquire（朝最后已知位置；超时/禁搜 → need_reallocation）
    └─ hold_fallback
"""

from .harness_interface import (
    ActionKind, FeedbackReason, Phase, PlatformType, TaskType)
from .base import Behavior, BehaviorTree, Node, Selector, Sequence
from .blackboard import Blackboard
from .helpers import (_bearing, _dist, _emit, _own, _own_course, _param,
                      _target_track, hold_fn, safety_hold_fn, target_visible)
from .status import (STANDOFF_DEFAULT_M, Status, USV_APPROACH_SPEED,
                     USV_ORBIT_SPEED)


def _usv_hold_condition(bb: Blackboard) -> Status:
    """无目标或 HOLD_POSITION → 待命"""
    if (bb.get("task.task_type") == TaskType.HOLD_POSITION
            or bb.get("task.target_id") is None):
        return hold_fn(bb, uav=False)
    return Status.FAILURE


def _usv_approach(bb: Blackboard) -> Status:
    """远离 → APPROACH_TARGET；进入 standoff 圈 → SUCCESS（进锁距）"""
    tr = _target_track(bb)
    if tr is None:
        return Status.FAILURE
    own = _own(bb)
    tpos = tr.get("position")
    standoff = _param(bb, "standoff_distance", STANDOFF_DEFAULT_M)
    if _dist(own, tpos) <= standoff:
        return Status.SUCCESS
    _emit(bb, ActionKind.APPROACH_TARGET, target_id=bb.get("task.target_id"),
          course=_bearing(own, tpos),
          speed=_param(bb, "approach_speed", USV_APPROACH_SPEED),
          phase=Phase.approach, branch="approach")
    return Status.RUNNING


def _usv_send_lock(bb: Blackboard) -> Status:
    """进锁距 → 发一次 ENGAGE_TARGET(lock)（同 tick 继续 orbit）；
    已锁定（is_locking）或已发过 → 不再重复 lock（保护 300s 锁链）"""
    state = bb.get("ctx.platform_state") or {}
    if state.get("is_locking") or bb.get("lock_sent"):
        return Status.SUCCESS
    _emit(bb, ActionKind.ENGAGE_TARGET, target_id=bb.get("task.target_id"),
          phase=Phase.engage, branch="engage")
    bb.set("lock_sent", True)
    return Status.SUCCESS


def _usv_orbit(bb: Blackboard) -> Status:
    """standoff move：距离圈内切线航行，圈外收近，圈内拉远"""
    tr = _target_track(bb)
    if tr is None:
        return Status.FAILURE
    own = _own(bb)
    tpos = tr.get("position")
    b = _bearing(own, tpos)
    d = _dist(own, tpos)
    standoff = _param(bb, "standoff_distance", STANDOFF_DEFAULT_M)
    if d < standoff * 0.8:
        course = (b + 180) % 360          # 圈内 → 拉远
    elif d > standoff * 1.2:
        course = b                        # 圈外 → 收近
    else:
        course = (b + 90) % 360           # 圈带 → 切线环绕
    _emit(bb, ActionKind.ORBIT_TARGET, target_id=bb.get("task.target_id"),
          course=course, speed=_param(bb, "orbit_speed", USV_ORBIT_SPEED),
          phase=Phase.orbit, branch="orbit")
    return Status.RUNNING


def _usv_reacquire(bb: Blackboard) -> Status:
    """目标丢失 → 局部 reacquire（同 target）；超时/禁搜 → need_reallocation"""
    if not bb.get("task.allow_local_reacquire"):
        bb.set("need_reallocation", True)
        bb.set("reason", FeedbackReason.blocked)
        return Status.RUNNING
    lost_at = bb.get("lost_at")
    sim_time = bb.get("ctx.sim_time")
    max_search = bb.get("task.max_search_time") or 60.0
    if lost_at is not None and sim_time - float(lost_at) >= float(max_search):
        bb.set("need_reallocation", True)
        bb.set("reason", FeedbackReason.target_lost_timeout)
        return Status.RUNNING
    # 朝最后已知位置搜（无则保持当前航向）
    last = bb.get("last_seen_pos")
    course = _bearing(_own(bb), last) if last else _own_course(bb)
    _emit(bb, ActionKind.REACQUIRE, target_id=bb.get("task.target_id"),
          course=course,
          speed=_param(bb, "approach_speed", USV_APPROACH_SPEED),
          phase=Phase.reacquire, branch="reacquire")
    bb.set("reason", FeedbackReason.target_lost)
    return Status.RUNNING


def _usv_root() -> Node:
    return Selector("root", [
        Behavior("safety_hold", lambda bb: safety_hold_fn(bb, uav=False)),
        Selector("task", [
            Behavior("hold_condition", _usv_hold_condition),
            # visible → Sequence(approach → engage)；条件在序列内，
            # 目标丢失时序列 FAILURE → 落到 reacquire
            Sequence("visible_engage", [
                Behavior("target_visible", target_visible),
                Sequence("approach_engage", [
                    Behavior("approach", _usv_approach),
                    Sequence("engage", [
                        Behavior("send_lock", _usv_send_lock),
                        Behavior("orbit", _usv_orbit),
                    ], memory=True),
                ]),
            ]),
            Behavior("reacquire", _usv_reacquire),
        ]),
        Behavior("hold_fallback", lambda bb: hold_fn(bb, uav=False)),
    ], memory=False)   # 根 Selector 非 memory：每 tick 重查 safety guard


def build_usv_tree(platform_id: str) -> BehaviorTree:
    """USV 最小真实树（INTERCEPT_LOCK / ENGAGE_TARGET / HOLD_POSITION）"""
    bb = Blackboard()
    bb.set("platform_id", platform_id)
    bb.set("platform_type", PlatformType.USV)
    return BehaviorTree(_usv_root(), bb)
