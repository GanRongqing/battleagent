"""
真实行为树 — 与《BT_HARNESS_INTERFACE_REFERENCE.md》§5 一致（2026-08）

内容：
  1. 行为树框架：Status / Node / Selector / Sequence / Behavior / BehaviorTree（含 memory）
  2. build_usv_tree / build_uav_tree — 最小真实树（无 allocator，target 不可变）
  3. BTBridge — ExecutionContext ↔ Blackboard 唯一翻译处（网络职责为 0：
     pre_tick 只填黑板，post_tick 只打包，不直写仿真）
  4. make_executive_tree — 按平台类型构造带黑板的树实例

树结构（§5）：
  root（Selector 非 memory，保证每 tick 重查 safety guard）
    ├─ safety_hold：safety_feedback 含 REJECTED/OVERRIDDEN → HOLD + reason
    ├─ USV：visible → Sequence(approach → engage)   # 远离→approach；进锁距→先发一次
    │                lock 再 standoff orbit；已锁定不再重复 lock（保护 300s 锁链）
    │        lost  → reacquire（memory；allow_local_reacquire；超时 need_reallocation）
    │        无目标 → hold_fallback
    ├─ UAV：cooperative_lock → Sequence(approach → orbit)
    │        situation_update → navigate（docked 时先 LAUNCH）
    │        return_recharge → Sequence(return → dock)
    └─ hold_fallback

Target 不可变：所有 target 引用来自 blackboard.task.target_id（TaskCommand 指派）；
树内无 allocator，环境里更近/置信更高的目标都不会改变锁定对象。

引擎事实（数值来源，可经 TaskCommand.constraints 覆盖）：
  雷达 100km > 锁定射程 40km；射程外先接近至 standoff（默认 35km）再锁定/环绕；
  UAV 返航至母舰 5km 内转降落；航点到达判定 10km。
"""

from __future__ import annotations

import math
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from .harness_interface import (
    ActionKind, ActionRequest, BTStepResult, ExecutionContext,
    FeedbackReason, Phase, PlatformType, TaskFeedback, TaskStatus, TaskType)

# ============================================================================
# 引擎事实常量（默认值，可经 TaskCommand.constraints 覆盖）
# ============================================================================

STANDOFF_DEFAULT_M = 35_000.0   # 接近机动目标距离：进入传感与武器作用圈
GOTO_RANGE_M = 10_000.0         # UAV 飞赴任务点到达判定半径
LAND_RANGE_M = 5_000.0          # UAV 返航至母舰附近后转入降落请求的距离
USV_APPROACH_SPEED = 20.0       # USV 接近速度 (m/s)
USV_ORBIT_SPEED = 20.0          # USV 环绕 standoff 速度 (m/s)
USV_PATROL_SPEED = 20.0         # USV 待命/巡逻速度 (m/s)
UAV_CRUISE_SPEED = 100.0        # UAV 巡航速度 (m/s)
UAV_TAKEOFF_COURSE = 90.0       # UAV 起飞航向（度）


# ============================================================================
# 行为树框架
# ============================================================================


class Status(str, Enum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


class Blackboard:
    """黑板 — 树内共享记忆（含任务键与执行上下文）"""

    def __init__(self) -> None:
        self._d: Dict[str, Any] = {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._d.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._d[key] = value


class Node:
    """节点基类"""

    def __init__(self, name: str = "node") -> None:
        self.name = name

    def tick(self, bb: Blackboard) -> Status:
        raise NotImplementedError

    def reset(self) -> None:
        """清 memory 分支（默认无状态）"""


class Behavior(Node):
    """叶子行为 — 闭包实现具体逻辑"""

    def __init__(self, name: str, fn: Callable[[Blackboard], Status]) -> None:
        super().__init__(name)
        self._fn = fn

    def tick(self, bb: Blackboard) -> Status:
        return self._fn(bb)


class Sequence(Node):
    """顺序节点 — 依次执行子节点；FAILURE 即失败，RUNNING 即挂起

    memory=True: 记住 RUNNING 子节点下标，下次从该子节点继续（如
    engage 序列：SendLock 发过一次后不再重复）。"""

    def __init__(self, name: str, children: List[Node],
                 memory: bool = False) -> None:
        super().__init__(name)
        self.children = children
        self.memory = memory
        self._idx = 0

    def tick(self, bb: Blackboard) -> Status:
        start = self._idx if self.memory else 0
        for i in range(start, len(self.children)):
            st = self.children[i].tick(bb)
            if st == Status.FAILURE:
                if self.memory:
                    self._idx = 0
                return Status.FAILURE
            if st == Status.RUNNING:
                if self.memory:
                    self._idx = i
                return Status.RUNNING
        if self.memory:
            self._idx = 0
        return Status.SUCCESS

    def reset(self) -> None:
        self._idx = 0
        for c in self.children:
            c.reset()


class Selector(Node):
    """选择节点 — 依次尝试子节点；任一非 FAILURE 即通过（重查语义）

    memory=True: 记住 RUNNING 子节点下标（如 reacquire 持续执行）。"""

    def __init__(self, name: str, children: List[Node],
                 memory: bool = False) -> None:
        super().__init__(name)
        self.children = children
        self.memory = memory
        self._idx = 0

    def tick(self, bb: Blackboard) -> Status:
        start = self._idx if self.memory else 0
        for i in range(start, len(self.children)):
            st = self.children[i].tick(bb)
            if st != Status.FAILURE:
                if self.memory:
                    self._idx = i
                return st
        if self.memory:
            self._idx = 0
        return Status.FAILURE

    def reset(self) -> None:
        self._idx = 0
        for c in self.children:
            c.reset()


class BehaviorTree:
    """树实例 — 树记忆在实例内部（blackboard），不暴露树外"""

    def __init__(self, root: Node, blackboard: Optional[Blackboard] = None) -> None:
        self.root = root
        self.blackboard = blackboard or Blackboard()
        self.active_task = None     # 当前任务命令（submit_task 写入）

    def tick(self) -> Status:
        return self.root.tick(self.blackboard)

    def reset(self) -> None:
        self.root.reset()


# ============================================================================
# 树内工具
# ============================================================================


def _pos(v: Any) -> Tuple[float, float]:
    """[x, y, z] → (x, y)"""
    if not v:
        return (0.0, 0.0)
    return (float(v[0]), float(v[1]))


def _dist(a: Any, b: Any) -> float:
    ax, ay = _pos(a)
    bx, by = _pos(b)
    return math.hypot(bx - ax, by - ay)


def _bearing(a: Any, b: Any) -> float:
    """a → b 方位角（0=北，顺时针）— 笛卡尔坐标 atan2(dx, dy)"""
    if not a or not b:
        return 0.0
    dx = float(b[0]) - float(a[0])
    dy = float(b[1]) - float(a[1])
    return (math.degrees(math.atan2(dx, dy)) + 360) % 360


def _param(bb: Blackboard, key: str, default: float) -> float:
    """任务约束优先，缺省用树内默认值"""
    v = bb.get("task.constraints") or {}
    val = v.get(key, default)
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _own(bb: Blackboard) -> Tuple[float, float]:
    state = bb.get("ctx.platform_state") or {}
    return _pos(state.get("position"))


def _target_track(bb: Blackboard) -> Optional[Dict[str, Any]]:
    target = bb.get("task.target_id")
    if not target:
        return None
    tracks = bb.get("ctx.tracks") or {}
    tr = tracks.get(target)
    if not tr or not tr.get("visible"):
        return None
    return tr


def _emit(bb: Blackboard, kind: ActionKind, *, target_id: Optional[str] = None,
          waypoint: Optional[Tuple[float, float]] = None,
          course: Optional[float] = None, speed: Optional[float] = None,
          meta: Optional[Dict[str, Any]] = None,
          phase: Optional[Phase] = None, branch: Optional[str] = None) -> None:
    """向本 tick 动作列表追加 ActionRequest（post_tick 打包输出）"""
    bb.get("actions").append(ActionRequest(
        platform_id=bb.get("platform_id"), action_kind=kind,
        target_id=target_id, waypoint=waypoint, course=course, speed=speed,
        meta=meta or {}))
    if phase is not None:
        bb.set("phase", phase)
    if branch is not None:
        bb.set("active_branch", branch)


def _safety_verdicts(bb: Blackboard) -> List[str]:
    """本平台上一 tick 动作的 safety 判定（action_text 以平台名开头）"""
    pid = bb.get("platform_id")
    safety = bb.get("ctx.safety") or {}
    return [v for k, v in safety.items() if k.startswith(f"{pid} ")]


# ============================================================================
# 通用行为
# ============================================================================


def _safety_hold_fn(bb: Blackboard, *, uav: bool) -> Status:
    """safety_hold：REJECTED/OVERRIDDEN → HOLD（下 tick 不再重复被拒 primitive）"""
    verdicts = _safety_verdicts(bb)
    if "REJECTED" in verdicts or "OVERRIDDEN" in verdicts:
        reason = (FeedbackReason.safety_override if "OVERRIDDEN" in verdicts
                  else FeedbackReason.safety_rejected)
        bb.set("reason", reason)
        if uav:
            _emit(bb, ActionKind.HOLD, course=_own_course(bb), speed=0.0,
                  phase=Phase.hold, branch="safety_hold")
        else:
            _emit(bb, ActionKind.HOLD, course=_own_course(bb),
                  speed=_param(bb, "patrol_speed", USV_PATROL_SPEED),
                  phase=Phase.hold, branch="safety_hold")
        return Status.RUNNING
    return Status.FAILURE


def _own_course(bb: Blackboard) -> float:
    state = bb.get("ctx.platform_state") or {}
    try:
        return float(state.get("heading", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def _hold_fn(bb: Blackboard, *, uav: bool) -> Status:
    """hold_fallback：待命/巡逻（USV 保持移动；UAV 悬停速度 0）"""
    if uav:
        _emit(bb, ActionKind.HOLD, course=_own_course(bb), speed=0.0,
              phase=Phase.hold, branch="hold")
    else:
        _emit(bb, ActionKind.HOLD, course=_own_course(bb),
              speed=_param(bb, "patrol_speed", USV_PATROL_SPEED),
              phase=Phase.hold, branch="hold")
    return Status.RUNNING


def _task_type_is(bb: Blackboard, task_type: TaskType) -> Status:
    return (Status.SUCCESS
            if bb.get("task.task_type") == task_type else Status.FAILURE)


# ============================================================================
# USV 树（INTERCEPT_LOCK / ENGAGE_TARGET / HOLD_POSITION）
# ============================================================================


def _usv_hold_condition(bb: Blackboard) -> Status:
    """无目标或 HOLD_POSITION → 待命"""
    if (bb.get("task.task_type") == TaskType.HOLD_POSITION
            or bb.get("task.target_id") is None):
        return _hold_fn(bb, uav=False)
    return Status.FAILURE


def _target_visible(bb: Blackboard) -> Status:
    return (Status.SUCCESS if _target_track(bb) is not None
            else Status.FAILURE)


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


# ============================================================================
# UAV 树（COOPERATIVE_LOCK / SITUATION_UPDATE / RETURN_RECHARGE / HOLD_POSITION）
# ============================================================================


def _uav_base_name(bb: Blackboard) -> str:
    """母舰名：约束 base 优先，其次平台状态记忆（飞行中引擎 home_name 为空）"""
    constraints = bb.get("task.constraints") or {}
    base = constraints.get("base")
    if base:
        return str(base)
    state = bb.get("ctx.platform_state") or {}
    return state.get("home_name") or bb.get("uav.home") or ""


def _uav_base_track(bb: Blackboard) -> Optional[Dict[str, Any]]:
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
    """降落：显式 land_uav；停靠成功后下一 tick 由 docked_done 判完成"""
    state = bb.get("ctx.platform_state") or {}
    if state.get("is_at_usv"):
        bb.set("task.completed", True)
        bb.set("reason", FeedbackReason.task_completed)
        return Status.SUCCESS
    _emit(bb, ActionKind.LAND_OR_DOCK, meta={"base": _uav_base_name(bb)},
          phase=Phase.dock, branch="dock")
    return Status.RUNNING


# ============================================================================
# 树构建（§5）
# ============================================================================


def _usv_root() -> Node:
    return Selector("root", [
        Behavior("safety_hold", lambda bb: _safety_hold_fn(bb, uav=False)),
        Selector("task", [
            Behavior("hold_condition", _usv_hold_condition),
            # visible → Sequence(approach → engage)；条件在序列内，
            # 目标丢失时序列 FAILURE → 落到 reacquire
            Sequence("visible_engage", [
                Behavior("target_visible", _target_visible),
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
        Behavior("hold_fallback", lambda bb: _hold_fn(bb, uav=False)),
    ], memory=False)   # 根 Selector 非 memory：每 tick 重查 safety guard


def _uav_root() -> Node:
    return Selector("root", [
        Behavior("safety_hold", lambda bb: _safety_hold_fn(bb, uav=True)),
        Selector("task", [
            Sequence("hold_position", [
                Behavior("type_hold", lambda bb: _task_type_is(bb, TaskType.HOLD_POSITION)),
                Behavior("hover", lambda bb: _hold_fn(bb, uav=True)),
            ]),
            Sequence("cooperative_lock", [
                Behavior("type_coop", lambda bb: _task_type_is(bb, TaskType.COOPERATIVE_LOCK)),
                Behavior("launch_if_docked", _uav_launch_if_docked),
                Behavior("approach", _uav_approach),
                Behavior("orbit", _uav_orbit),
            ]),
            Sequence("situation_update", [
                Behavior("type_sit", lambda bb: _task_type_is(bb, TaskType.SITUATION_UPDATE)),
                Behavior("launch_if_docked", _uav_launch_if_docked),
                Behavior("navigate", _uav_navigate),
            ]),
            Selector("return_recharge", [
                Sequence("docked_done", [
                    Behavior("type_return", lambda bb: _task_type_is(bb, TaskType.RETURN_RECHARGE)),
                    Behavior("docked", _uav_docked_done),
                ]),
                Sequence("return_dock", [
                    Behavior("type_return", lambda bb: _task_type_is(bb, TaskType.RETURN_RECHARGE)),
                    Behavior("return_home", _uav_return),
                    Behavior("dock", _uav_dock),
                ]),
            ]),
        ]),
        Behavior("hold_fallback", lambda bb: _hold_fn(bb, uav=True)),
    ], memory=False)


def build_usv_tree(platform_id: str) -> BehaviorTree:
    """USV 最小真实树（INTERCEPT_LOCK / ENGAGE_TARGET / HOLD_POSITION）"""
    bb = Blackboard()
    bb.set("platform_id", platform_id)
    bb.set("platform_type", PlatformType.USV)
    return BehaviorTree(_usv_root(), bb)


def build_uav_tree(platform_id: str) -> BehaviorTree:
    """UAV 最小真实树（COOPERATIVE_LOCK / SITUATION_UPDATE /
    RETURN_RECHARGE / HOLD_POSITION）"""
    bb = Blackboard()
    bb.set("platform_id", platform_id)
    bb.set("platform_type", PlatformType.UAV)
    return BehaviorTree(_uav_root(), bb)


def make_executive_tree(platform_id: str,
                        platform_type: PlatformType) -> BehaviorTree:
    """按平台类型构造执行器树实例"""
    if PlatformType(platform_type) == PlatformType.UAV:
        return build_uav_tree(platform_id)
    return build_usv_tree(platform_id)


# ============================================================================
# BTBridge — ExecutionContext ↔ Blackboard（网络职责为 0）
# ============================================================================


class BTBridge:
    """合法 runtime 快照 ↔ 黑板 的唯一翻译处。

    pre_tick:  ExecutionContext → Blackboard（只填黑板，不直写仿真）
    post_tick: Blackboard → BTStepResult（只打包，不直写仿真）
    任务键（task.*）由 submit_task 写入黑板，本桥只刷新运行时上下文。
    """

    @staticmethod
    def pre_tick(tree: BehaviorTree, context: ExecutionContext) -> None:
        bb = tree.blackboard
        bb.set("ctx.sim_time", context.sim_time)
        bb.set("ctx.platform_state", dict(context.platform_state))
        bb.set("ctx.tracks", dict(context.tracks))
        bb.set("ctx.safety", dict(context.safety_feedback or {}))
        bb.set("ctx.controller_feedback", context.controller_feedback)

        # 目标可见性记账（lost_at / last_seen_pos 供 reacquire 使用）
        target = bb.get("task.target_id")
        bb.set("target_visible", False)
        bb.set("target_confidence", 0.0)
        if target:
            tr = (context.tracks or {}).get(target)
            if tr and tr.get("visible"):
                bb.set("target_visible", True)
                bb.set("target_confidence", float(tr.get("confidence", 1.0)))
                bb.set("last_seen_pos", tr.get("position"))
                bb.set("lost_at", None)
            elif bb.get("lost_at") is None:
                bb.set("lost_at", context.sim_time)

        # 每 tick 重置输出区
        bb.set("actions", [])
        bb.set("need_reallocation", False)
        bb.set("reason", FeedbackReason.none)
        bb.set("phase", None)
        bb.set("active_branch", None)

    @staticmethod
    def post_tick(tree: BehaviorTree, context: ExecutionContext,
                  root_status: Status) -> BTStepResult:
        bb = tree.blackboard
        # 同平台同 tick 每通道至多 1 个请求（防御性去重，树本身已保证）
        seen = set()
        actions: List[ActionRequest] = []
        for a in bb.get("actions") or []:
            if a.channel in seen:
                continue
            seen.add(a.channel)
            actions.append(a)

        feedback = TaskFeedback(
            platform_id=context.platform_id,
            task_id=bb.get("task.task_id") or "",
            status=bb.get("task.status") or TaskStatus.RUNNING,
            phase=(bb.get("phase") or Phase.hold).value,
            target_id=bb.get("task.target_id"),
            target_visible=bool(bb.get("target_visible")),
            target_confidence=float(bb.get("target_confidence") or 0.0),
            need_reallocation=bool(bb.get("need_reallocation")),
            reason_code=bb.get("reason") or FeedbackReason.none)
        return BTStepResult(
            tick_id=0, platform_id=context.platform_id,
            root_status=root_status.value, action_requests=actions,
            task_feedback=feedback, active_branch=bb.get("active_branch"))
