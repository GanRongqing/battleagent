"""
Harness ↔ 行为树 接口层 — 与《BT_HARNESS_INTERFACE_REFERENCE.md》一致（2026-08）

本模块定义 Harness 接入行为树的全部契约：枚举、数据结构、
PlatformExecutive 抽象、BTPlatformExecutive 实现（submit/cancel/tick 生命周期）、
BTActionAdapter（ActionRequest → /apply payload）。

只依赖标准库；真实行为树经 harness.make_executive_tree 惰性引入，
避免接口层与树实现循环依赖。任何接入方以仓库根 BT_HARNESS_INTERFACE_REFERENCE.md
为准，本文件是其可执行实现。

数据流（HARNESS_BT_MODE）:
  Harness(allocator) ──TaskCommand──→ submit_task → TaskAck
  Harness ──CancelTaskRequest───────→ cancel_task → TaskAck
  Harness ──ExecutionContext────────→ tick → BTStepResult(action_requests + task_feedback)
  动作经 BTActionAdapter → /apply → simulator（只有 Harness 一个 writer）
"""

from __future__ import annotations

import abc
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# ============================================================================
# 枚举（§3 全表）
# ============================================================================


class PlatformType(str, Enum):
    USV = "USV"   # 水面无人艇
    UAV = "UAV"   # 无人机


class TaskType(str, Enum):
    """任务族"""
    INTERCEPT_LOCK = "INTERCEPT_LOCK"      # USV 拦截并锁定指派目标
    ENGAGE_TARGET = "ENGAGE_TARGET"        # USV 交战/攻击指派目标
    HOLD_POSITION = "HOLD_POSITION"        # 两者 待命/巡逻
    COOPERATIVE_LOCK = "COOPERATIVE_LOCK"  # UAV 协同锁定（standoff 环绕）
    SITUATION_UPDATE = "SITUATION_UPDATE"  # UAV 态势更新（飞往航点搜索）
    RETURN_RECHARGE = "RETURN_RECHARGE"    # UAV 返航充电


class TaskStatus(str, Enum):
    """任务状态：PENDING → ACCEPTED → RUNNING → COMPLETED / REJECTED / CANCELLED"""
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class AckCode(str, Enum):
    """submit/cancel 应答码（§3）"""
    ACCEPTED = "ACCEPTED"                            # 新任务接受
    ACCEPTED_WITH_PREEMPTION = "ACCEPTED_WITH_PREEMPTION"  # 接受并抢占旧任务
    DUPLICATE_IGNORED = "DUPLICATE_IGNORED"          # 同 task_id + 同 revision
    STALE_REJECTED = "STALE_REJECTED"                # 更低 task/plan revision
    EXPIRED = "EXPIRED"                              # valid_until 已过
    INVALID_PLATFORM = "INVALID_PLATFORM"            # 平台名不匹配
    INVALID_TYPE = "INVALID_TYPE"                    # 平台类型不匹配
    BUSY = "BUSY"                                    # 不可抢占且非 safety override
    CANCELLED = "CANCELLED"                          # 取消成功
    NOT_FOUND = "NOT_FOUND"                          # 未找到匹配任务


class ActionKind(str, Enum):
    """BT 意图（§3）"""
    NAVIGATE_TO = "NAVIGATE_TO"
    APPROACH_TARGET = "APPROACH_TARGET"
    ORBIT_TARGET = "ORBIT_TARGET"
    TRACK_TARGET = "TRACK_TARGET"
    ENGAGE_TARGET = "ENGAGE_TARGET"
    RETURN_TO_BASE = "RETURN_TO_BASE"
    LAND_OR_DOCK = "LAND_OR_DOCK"
    HOLD = "HOLD"
    REACQUIRE = "REACQUIRE"
    LAUNCH = "LAUNCH"


class ActionChannel(str, Enum):
    """控制通道 — 同平台同 tick 每通道至多 1 个 ActionRequest"""
    NAVIGATION = "NAVIGATION"
    SENSOR = "SENSOR"
    WEAPON = "WEAPON"
    SYSTEM = "SYSTEM"


# ActionKind → ActionChannel 映射（§3 表）
ACTION_CHANNEL: Dict[ActionKind, ActionChannel] = {
    ActionKind.NAVIGATE_TO: ActionChannel.NAVIGATION,
    ActionKind.APPROACH_TARGET: ActionChannel.NAVIGATION,
    ActionKind.ORBIT_TARGET: ActionChannel.NAVIGATION,
    ActionKind.TRACK_TARGET: ActionChannel.NAVIGATION,
    ActionKind.RETURN_TO_BASE: ActionChannel.NAVIGATION,
    ActionKind.LAND_OR_DOCK: ActionChannel.NAVIGATION,
    ActionKind.HOLD: ActionChannel.NAVIGATION,
    ActionKind.LAUNCH: ActionChannel.NAVIGATION,
    ActionKind.REACQUIRE: ActionChannel.SENSOR,
    ActionKind.ENGAGE_TARGET: ActionChannel.WEAPON,
}


class FeedbackReason(str, Enum):
    """任务反馈原因码（§3）"""
    none = "none"
    target_lost = "target_lost"
    target_lost_timeout = "target_lost_timeout"
    need_reallocation = "need_reallocation"
    task_completed = "task_completed"
    safety_rejected = "safety_rejected"
    safety_override = "safety_override"
    unreachable = "unreachable"
    expired = "expired"
    not_yet_valid = "not_yet_valid"
    blocked = "blocked"
    preempted = "preempted"


class Phase(str, Enum):
    """执行阶段（§3）"""
    approach = "approach"
    orbit = "orbit"
    track = "track"
    engage = "engage"
    search = "search"
    return_ = "return"
    dock = "dock"
    hold = "hold"
    reacquire = "reacquire"


# ============================================================================
# 数据结构（§2 全字段）
# ============================================================================


@dataclass
class TaskCommand:
    """Harness → BT 的任务指派（§2.1）

    target_id 一旦指派即不可变：BT 内不允许自行重新决定"锁谁"，
    目标丢失只允许局部 reacquire（同 target），超时交回 Harness。
    """
    task_id: str
    platform_id: str
    platform_type: PlatformType
    task_type: TaskType
    target_id: Optional[str] = None
    role: str = "default"
    revision: int = 1                       # 同 task 更高 revision = 更新
    priority: int = 0
    plan_id: str = ""
    plan_revision: int = 1                  # 同 plan 更低 revision = 过期
    valid_from: Optional[float] = None      # 生效起始仿真秒
    valid_until: Optional[float] = None     # 失效仿真秒（之后 expired）
    preemptible: bool = True                # False 时仅 safety override 可抢占
    safety_override: bool = False           # 安全任务，可抢占任何任务
    allow_local_reacquire: bool = True      # 目标丢失时是否允许局部 reacquire
    max_search_time: float = 60.0           # 局部 reacquire 窗口（秒）
    constraints: Dict[str, Any] = field(default_factory=dict)  # 主要约束（waypoint/base/speed 等）


@dataclass
class TaskAck:
    """submit/cancel 的应答（§2.2）"""
    code: AckCode
    task_id: str
    platform_id: str
    message: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass
class CancelTaskRequest:
    """取消任务请求（§2.3）"""
    platform_id: str
    task_id: str
    reason: str = "cancel"


@dataclass
class ExecutionContext:
    """Harness → BT 每 tick 的合法 runtime 快照（§2.4）

    不得含 ground_truth / true_enemy_state / future_trajectory 等
    运行期不可获得信息；tracks 仅含合法观测（信念航迹）。
    """
    platform_id: str
    platform_type: PlatformType
    sim_time: float
    # 自身状态: position/speed/heading/is_alive；USV 另含 is_locking/locking_unit；
    # UAV 另含 is_at_usv（是否在舰上）/ home_name
    platform_state: Dict[str, Any] = field(default_factory=dict)
    # 信念航迹 {name: {position, visible, confidence, is_ship}}（仅合法观测；
    # is_ship=True 为友方舰船，供返航找母舰）
    tracks: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    controller_feedback: Optional[Dict[str, Any]] = None   # 上一个控制器结果
    safety_feedback: Optional[Dict[str, str]] = None       # {action_text: PASS/CLAMPED/MODIFIED/REJECTED/OVERRIDDEN}
    nearby_friendlies: List[Dict[str, Any]] = field(default_factory=list)
    hazards: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ActionRequest:
    """BT → Harness 意图级动作（§2.5）"""
    platform_id: str
    action_kind: ActionKind
    target_id: Optional[str] = None        # 必须与指派一致
    waypoint: Optional[Tuple[float, float]] = None
    course: Optional[float] = None         # 航向（度，正北 0 顺时针）
    speed: Optional[float] = None
    meta: Dict[str, Any] = field(default_factory=dict)  # 附加（如 UAV home/base）

    @property
    def channel(self) -> ActionChannel:
        """由 ACTION_CHANNEL 推导（同平台同 tick 每通道 ≤1 个请求）"""
        return ACTION_CHANNEL.get(self.action_kind, ActionChannel.SYSTEM)


@dataclass
class TaskFeedback:
    """BT → Harness 每 tick 反馈（§2.6）"""
    platform_id: str
    task_id: str
    status: TaskStatus
    phase: Optional[str] = None
    target_id: Optional[str] = None
    target_visible: bool = False
    target_confidence: float = 0.0
    need_reallocation: bool = False
    reason_code: FeedbackReason = FeedbackReason.none


@dataclass
class BTStepResult:
    """tick 的返回（§2.7）"""
    tick_id: int
    platform_id: str
    root_status: str = "IDLE"              # RUNNING / SUCCESS / FAILURE / IDLE
    action_requests: List[ActionRequest] = field(default_factory=list)
    task_feedback: Optional[TaskFeedback] = None
    active_branch: Optional[str] = None


# ============================================================================
# PlatformExecutive 契约（§1，对外接口，禁止改动）
# ============================================================================


class PlatformExecutive(abc.ABC):
    def submit_task(self, command: TaskCommand, now_sim: Optional[float] = None) -> TaskAck:
        ...

    def cancel_task(self, request: CancelTaskRequest) -> TaskAck:
        ...

    def tick(self, context: ExecutionContext) -> BTStepResult:
        ...


# ============================================================================
# BTPlatformExecutive — 每平台一个实例，包装一颗真实行为树
# ============================================================================


class BTPlatformExecutive(PlatformExecutive):
    """平台执行器（§4 生命周期语义 + §5 tick 语义）

    submit_task: 校验并登记任务（可带当前仿真秒做 expired 判定）；
                 把任务写入 blackboard / tree.active_task，不执行 tick。
    cancel_task: 取消 active task，重置 memory 分支，不销毁整棵树。
    tick:        严格包装 bt_bridge.pre_tick → tree.tick → bt_bridge.post_tick。
    """

    def __init__(self, platform_id: str, platform_type: PlatformType,
                 tree: Any = None):
        self.platform_id = platform_id
        self.platform_type = PlatformType(platform_type)
        self._tasks: Dict[str, TaskCommand] = {}      # task_id → TaskCommand
        self._active_task_id: Optional[str] = None
        self._tick_id = 0
        self._completed = False
        if tree is None:
            # 惰性引入真实树，避免接口层 ↔ 树实现循环依赖
            from .tree_manager import make_executive_tree
            tree = make_executive_tree(platform_id, self.platform_type)
        self.tree = tree

    # ─── 查询 ─────────────────────────────────────────────

    def active_tasks(self) -> List[Tuple[str, TaskCommand]]:
        """当前登记任务（task_id, command），含已被取代的非活动任务记录"""
        return list(self._tasks.items())

    @property
    def active_task(self) -> Optional[TaskCommand]:
        if self._active_task_id is None:
            return None
        return self._tasks.get(self._active_task_id)

    # ─── submit_task（§4 判定顺序）────────────────────────

    def submit_task(self, command: TaskCommand,
                    now_sim: Optional[float] = None) -> TaskAck:
        def _ack(code: AckCode, message: str = "") -> TaskAck:
            return TaskAck(code=code, task_id=command.task_id,
                           platform_id=command.platform_id, message=message)

        # 1. 平台名/类型核对
        if command.platform_id != self.platform_id:
            return _ack(AckCode.INVALID_PLATFORM,
                        f"平台名不匹配（执行器: {self.platform_id}）")
        try:
            ctype = PlatformType(command.platform_type)
        except ValueError:
            ctype = None
        if ctype != self.platform_type:
            return _ack(AckCode.INVALID_TYPE,
                        f"平台类型不匹配（执行器: {self.platform_type.value}）")

        # 2. valid_until 已过（可带当前仿真秒判定）
        if (now_sim is not None and command.valid_until is not None
                and now_sim > command.valid_until):
            return _ack(AckCode.EXPIRED,
                        f"任务已过期（valid_until={command.valid_until} < now={now_sim}）")

        # 3. 同 plan_id 且 plan_revision 更低 → 过期方案
        current = self.active_task
        if (current is not None and current.plan_id
                and command.plan_id == current.plan_id
                and command.plan_revision < current.plan_revision):
            return _ack(AckCode.STALE_REJECTED,
                        f"方案 {command.plan_id} 版本 {command.plan_revision} "
                        f"低于当前 {current.plan_revision}")

        # 4. 同 task_id 的重复/更新
        if command.task_id in self._tasks:
            old = self._tasks[command.task_id]
            if command.revision == old.revision:
                return _ack(AckCode.DUPLICATE_IGNORED,
                            "同 task_id + 同 revision 重复提交，忽略（不重初始化）")
            if command.revision < old.revision:
                return _ack(AckCode.STALE_REJECTED,
                            f"revision {command.revision} 低于已登记 {old.revision}")
            # revision 更高 → 作为更新接受
            self._register(command, preempted=None)
            return _ack(AckCode.ACCEPTED, f"任务更新（revision {command.revision}）")

        # 5. 不同 task_id（抢占裁决）
        if current is not None:
            allowed = (command.safety_override
                       or current.preemptible
                       or command.priority > current.priority)
            if not allowed:
                return _ack(AckCode.BUSY,
                            f"当前任务 {current.task_id} 不可抢占"
                            f"（preemptible={current.preemptible}, "
                            f"priority={current.priority}）")
            self._register(command, preempted=current)
            msg = ("安全任务抢占" if command.safety_override else
                   "高优先级抢占" if command.priority > current.priority else
                   "普通抢占")
            return _ack(AckCode.ACCEPTED_WITH_PREEMPTION,
                        f"{msg}旧任务 {current.task_id}")

        # 6. 无活动任务 → 直接接受
        self._register(command, preempted=None)
        return _ack(AckCode.ACCEPTED, "新任务接受")

    def _register(self, command: TaskCommand,
                  preempted: Optional[TaskCommand]) -> None:
        """登记任务：写 blackboard / tree.active_task；重置
        lost_since/reacquire/phase；root.reset() 清 memory 分支"""
        if preempted is not None:
            # 被抢占任务仅记录在案（tick 只反馈活动任务，抢断信息经 TaskAck 传达）
            preempted.status = TaskStatus.CANCELLED
            preempted.preempted_reason = FeedbackReason.preempted
        self._tasks[command.task_id] = command
        self._active_task_id = command.task_id
        self._completed = False
        command.status = TaskStatus.ACCEPTED
        # 任务键写入黑板（树内所有 target 引用来自 blackboard，无 allocator）
        bb = self.tree.blackboard
        bb.set("task.task_id", command.task_id)
        bb.set("task.task_type", command.task_type)
        bb.set("task.target_id", command.target_id)
        bb.set("task.role", command.role)
        bb.set("task.constraints", dict(command.constraints))
        bb.set("task.allow_local_reacquire", command.allow_local_reacquire)
        bb.set("task.max_search_time", command.max_search_time)
        bb.set("task.status", command.status)
        bb.set("task.completed", False)
        # 重置丢失/reacquire/phase 等树内记忆
        bb.set("lost_at", None)
        bb.set("last_seen_pos", None)
        bb.set("lock_sent", False)
        bb.set("phase", None)
        bb.set("need_reallocation", False)
        bb.set("reason", FeedbackReason.none)
        self.tree.active_task = command
        self.tree.reset()     # 清 memory 分支（仅在新任务/更新时）

    # ─── cancel_task ──────────────────────────────────────

    def cancel_task(self, request: CancelTaskRequest) -> TaskAck:
        if request.platform_id != self.platform_id:
            return TaskAck(code=AckCode.NOT_FOUND, task_id=request.task_id,
                           platform_id=self.platform_id,
                           message=f"平台 {request.platform_id} 上未找到任务")
        cmd = self._tasks.get(request.task_id)
        if cmd is None or self._active_task_id != request.task_id:
            return TaskAck(code=AckCode.NOT_FOUND, task_id=request.task_id,
                           platform_id=self.platform_id,
                           message="未找到匹配的活动任务")
        cmd.status = TaskStatus.CANCELLED
        self._active_task_id = None
        self._completed = False
        # 重置与该任务相关的 memory 分支，不销毁整棵树
        bb = self.tree.blackboard
        bb.set("task.task_id", None)
        bb.set("task.target_id", None)
        bb.set("task.status", None)
        bb.set("task.completed", False)
        bb.set("lost_at", None)
        bb.set("lock_sent", False)
        bb.set("phase", None)
        bb.set("need_reallocation", False)
        bb.set("reason", FeedbackReason.none)
        self.tree.active_task = None
        self.tree.reset()
        return TaskAck(code=AckCode.CANCELLED, task_id=request.task_id,
                       platform_id=self.platform_id,
                       message=f"已取消（{request.reason}）")

    # ─── tick（§5）────────────────────────────────────────

    def tick(self, context: ExecutionContext) -> BTStepResult:
        self._tick_id += 1
        tid = self._tick_id

        if self._active_task_id is None:
            return BTStepResult(tick_id=tid, platform_id=self.platform_id,
                                root_status="IDLE")
        cmd = self._tasks[self._active_task_id]

        # 已完成任务：锁存，不再产出动作（root 保持 SUCCESS）
        if self._completed:
            return BTStepResult(
                tick_id=tid, platform_id=self.platform_id, root_status="SUCCESS",
                task_feedback=self._feedback(cmd, TaskStatus.COMPLETED,
                                             FeedbackReason.task_completed,
                                             bb_phase="hold"))

        # valid_from / valid_until（tick 时判定）
        if cmd.valid_from is not None and context.sim_time < cmd.valid_from:
            return BTStepResult(
                tick_id=tid, platform_id=self.platform_id, root_status="IDLE",
                task_feedback=self._feedback(cmd, cmd.status,
                                             FeedbackReason.not_yet_valid,
                                             bb_phase="hold"))
        if cmd.valid_until is not None and context.sim_time > cmd.valid_until:
            cmd.status = TaskStatus.RUNNING
            return BTStepResult(
                tick_id=tid, platform_id=self.platform_id, root_status="IDLE",
                task_feedback=self._feedback(
                    cmd, cmd.status, FeedbackReason.expired,
                    bb_phase="hold", need_reallocation=True))

        # 正常路径：pre_tick → tree.tick → post_tick
        from .bt_bridge import BTBridge
        cmd.status = TaskStatus.RUNNING
        self.tree.blackboard.set("task.status", cmd.status)
        BTBridge.pre_tick(self.tree, context)
        root_status = self.tree.tick()
        result = BTBridge.post_tick(self.tree, context, root_status)
        result.tick_id = tid
        if root_status == "SUCCESS":
            cmd.status = TaskStatus.COMPLETED
            self._completed = True
            result.task_feedback.status = TaskStatus.COMPLETED
            result.task_feedback.reason_code = FeedbackReason.task_completed
            result.task_feedback.need_reallocation = False
        return result

    def _feedback(self, cmd: TaskCommand, status: TaskStatus,
                  reason: FeedbackReason, bb_phase: Optional[str] = None,
                  need_reallocation: bool = False) -> TaskFeedback:
        return TaskFeedback(
            platform_id=self.platform_id, task_id=cmd.task_id, status=status,
            phase=bb_phase, target_id=cmd.target_id,
            target_visible=False, target_confidence=0.0,
            need_reallocation=need_reallocation, reason_code=reason)

    # ─── 对局重置 ─────────────────────────────────────────

    def reset(self) -> None:
        """对局重开：清空全部任务与树状态"""
        self._tasks.clear()
        self._active_task_id = None
        self._completed = False
        self._tick_id = 0
        self.tree.active_task = None
        self.tree.reset()
        bb = self.tree.blackboard
        for key in ("task.task_id", "task.target_id", "task.status",
                    "task.completed", "lost_at", "last_seen_pos", "lock_sent",
                    "phase", "need_reallocation", "reason"):
            bb.set(key, None if key != "task.completed" else False)
        bb.set("reason", FeedbackReason.none)


# ============================================================================
# BTActionAdapter — ActionRequest → /apply payload（§6）
# ============================================================================


class BTActionAdapter:
    """ActionRequest[] → /apply 请求体 {"actions": [{action_text, action_type}]}

    映射表（§6）：导航类 → 移动/飞行（course/speed 由树算好）；
    ENGAGE → 锁定；LAUNCH → 起飞；LAND → 降落；HOLD → 移动/飞行。
    数值格式与 /apply 解析约定一致（整数不带小数点，浮点保留 1 位）。

    无预设策略数值：数值全部来自动作请求（树内计算 = 任务 constraints
    优先、引擎事实常量兜底）与仿真状态；数值缺失的动作不产出
    （to_action_item 返回 None，由调用方跳过），不发明默认值。
    """

    def to_apply_payload(self, requests: List[ActionRequest]) -> Dict[str, Any]:
        items = [self.to_action_item(r) for r in requests]
        return {"actions": [i for i in items if i is not None]}

    def to_action_item(self, r: ActionRequest) -> Optional[Dict[str, str]]:
        kind = r.action_kind
        name = r.platform_id
        if kind == ActionKind.ENGAGE_TARGET:
            if not r.target_id:
                return None
            return {"action_text": f"{name} 锁定 {r.target_id}",
                    "action_type": "lock"}
        if kind == ActionKind.LAUNCH:
            home = r.meta.get("home")
            if not home or r.speed is None or r.course is None:
                return None
            return {"action_text":
                    f"{name} 从 {home} 起飞 "
                    f"target_speed={_fmt(r.speed)} "
                    f"target_course={_fmt(r.course)}",
                    "action_type": "launch_uav"}
        if kind == ActionKind.LAND_OR_DOCK:
            base = r.meta.get("base") or r.target_id
            if not base:
                return None
            return {"action_text": f"{name} 降落到 {base}",
                    "action_type": "land_uav"}
        # NAVIGATE_TO / APPROACH / ORBIT / TRACK / REACQUIRE / RETURN / HOLD
        if r.speed is None or r.course is None:
            return None
        verb = "飞行" if self._is_uav(r) else "移动"
        return {"action_text":
                f"{name} {verb} target_speed={_fmt(r.speed)} "
                f"target_course={_fmt(r.course)}",
                "action_type": "fly" if self._is_uav(r) else "move"}

    @staticmethod
    def _is_uav(r: ActionRequest) -> bool:
        # UAV 平台名约定 white_uavN；也可从 meta 显式声明
        return bool(r.meta.get("uav")) or "uav" in r.platform_id.lower()


def _fmt(v: float) -> str:
    """数值格式化：整数不带小数点，浮点保留 1 位"""
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    return f"{v:.1f}" if isinstance(v, float) else str(v)


# ============================================================================
# 接口单测专用 stub（不进生产路径）
# ============================================================================


class StubBehaviorTree:
    """树 stub：只记录 blackboard，tick 恒返回 RUNNING"""

    def __init__(self):
        from .blackboard import Blackboard
        self.blackboard = Blackboard()
        self.active_task = None

    def tick(self) -> str:
        return "RUNNING"

    def reset(self) -> None:
        pass


class StubBTBridge:
    """桥 stub：pre_tick 把上下文写入黑板；post_tick 返回空结果"""

    @staticmethod
    def pre_tick(tree, context) -> None:
        bb = tree.blackboard
        bb.set("ctx.sim_time", context.sim_time)
        bb.set("ctx.platform_state", context.platform_state)
        bb.set("ctx.tracks", context.tracks)
        bb.set("ctx.safety", context.safety_feedback or {})
        bb.set("actions", [])

    @staticmethod
    def post_tick(tree, context, root_status) -> BTStepResult:
        bb = tree.blackboard
        return BTStepResult(
            tick_id=0, platform_id=context.platform_id,
            root_status=root_status, action_requests=[],
            task_feedback=TaskFeedback(
                platform_id=context.platform_id,
                task_id=bb.get("task.task_id") or "",
                status=bb.get("task.status") or TaskStatus.RUNNING),
            active_branch=bb.get("phase"))
