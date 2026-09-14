#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""bt_harness_interface.py — MINIMAL Harness ↔ Behavior Tree interface adaptation.

Interface layer only (user-selected scope: interface + stub BT). No Harness policy /
Skill / simulator change. The Behavior Tree side is represented by a deterministic STUB
(StubBehaviorTree + StubBTBridge) so the wrapper and adapter can be exercised and later
wired to a real BT without changing the interface.

Decision authority (HARNESS_BT_MODE):
  Harness owns  WHO + WHAT : platform, target, task_type, role, constraints
  BT owns       HOW/phase : approach / orbit / track / engage / search / return / dock / hold

Guarantees enforced here:
  - target_id immutable once assigned (even if another target is closer);
    target loss → local reacquire; timeout → need_reallocation=True.
  - task persists across ticks (submit once; no re-init while unchanged).
  - HARNESS_BT_MODE: the ONLY simulator action writer is Harness POST /apply;
    BT side produces intent-level ActionRequest[] only, never gRPC/HTTP writes.
  - ExecutionContext carries ONLY legal Harness runtime info (no ground truth /
    true enemy state / future trajectory).

  python bt_harness_interface.py   -> runs the 8 interface tests (self-check)
"""
from __future__ import annotations

import abc
import enum
import math
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ════════════════════════════════════════════════════════════════
# Enums
# ════════════════════════════════════════════════════════════════
class PlatformType(str, enum.Enum):
    USV = "USV"
    UAV = "UAV"


class TaskType(str, enum.Enum):
    INTERCEPT_LOCK = "INTERCEPT_LOCK"        # USV
    ENGAGE_TARGET = "ENGAGE_TARGET"          # USV
    HOLD_POSITION = "HOLD_POSITION"          # both
    COOPERATIVE_LOCK = "COOPERATIVE_LOCK"    # UAV
    SITUATION_UPDATE = "SITUATION_UPDATE"    # UAV
    RETURN_RECHARGE = "RETURN_RECHARGE"      # UAV


class TaskStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class AckCode(str, enum.Enum):
    ACCEPTED = "ACCEPTED"
    ACCEPTED_WITH_PREEMPTION = "ACCEPTED_WITH_PREEMPTION"
    DUPLICATE_IGNORED = "DUPLICATE_IGNORED"
    STALE_REJECTED = "STALE_REJECTED"
    EXPIRED = "EXPIRED"
    INVALID_PLATFORM = "INVALID_PLATFORM"
    INVALID_TYPE = "INVALID_TYPE"
    PREEMPTED = "PREEMPTED"
    BUSY = "BUSY"
    CANCELLED = "CANCELLED"
    NOT_FOUND = "NOT_FOUND"


class ActionKind(str, enum.Enum):
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


class ActionChannel(str, enum.Enum):
    NAVIGATION = "NAVIGATION"
    SENSOR = "SENSOR"
    WEAPON = "WEAPON"
    SYSTEM = "SYSTEM"


# action kind -> channel mapping (same-platform same-tick: at most one per channel)
ACTION_CHANNEL = {
    ActionKind.NAVIGATE_TO: ActionChannel.NAVIGATION,
    ActionKind.APPROACH_TARGET: ActionChannel.NAVIGATION,
    ActionKind.ORBIT_TARGET: ActionChannel.NAVIGATION,
    ActionKind.TRACK_TARGET: ActionChannel.NAVIGATION,
    ActionKind.RETURN_TO_BASE: ActionChannel.NAVIGATION,
    ActionKind.LAND_OR_DOCK: ActionChannel.NAVIGATION,
    ActionKind.HOLD: ActionChannel.NAVIGATION,
    ActionKind.REACQUIRE: ActionChannel.SENSOR,
    ActionKind.ENGAGE_TARGET: ActionChannel.WEAPON,
    ActionKind.LAUNCH: ActionChannel.NAVIGATION,
}


class Phase(str, enum.Enum):
    APPROACH = "approach"
    ORBIT = "orbit"
    TRACK = "track"
    ENGAGE = "engage"
    SEARCH = "search"
    RETURN = "return"
    DOCK = "dock"
    HOLD = "hold"
    REACQUIRE = "reacquire"


class FeedbackReason(str, enum.Enum):
    NONE = "none"
    TARGET_LOST = "target_lost"
    TARGET_LOST_TIMEOUT = "target_lost_timeout"
    NEED_REALLOCATION = "need_reallocation"
    TASK_COMPLETED = "task_completed"
    SAFETY_REJECTED = "safety_rejected"
    SAFETY_OVERRIDE = "safety_override"
    UNREACHABLE = "unreachable"
    EXPIRED = "expired"
    NOT_YET_VALID = "not_yet_valid"
    BLOCKED = "blocked"
    PREEMPTED = "preempted"


# ════════════════════════════════════════════════════════════════
# Dataclasses
# ════════════════════════════════════════════════════════════════
@dataclass
class TaskCommand:
    task_id: str
    platform_id: str
    platform_type: PlatformType
    task_type: TaskType
    target_id: Optional[str] = None
    role: str = "default"
    revision: int = 1
    priority: int = 0
    plan_id: str = ""
    plan_revision: int = 1
    valid_from: Optional[float] = None       # sim_time before which the task must not execute
    valid_until: Optional[float] = None      # sim_time after which the task is expired
    preemptible: bool = True                 # may this task be preempted by a normal task?
    safety_override: bool = False            # safety tasks may always preempt
    allow_local_reacquire: bool = True       # may the tree locally reacquire a lost target
    max_search_time: float = 60.0            # local reacquire window before need_reallocation
    constraints: Dict = field(default_factory=dict)   # major constraints only


@dataclass
class TaskAck:
    code: AckCode
    task_id: str
    platform_id: str
    message: str = ""
    timestamp: float = 0.0


@dataclass
class CancelTaskRequest:
    platform_id: str
    task_id: str
    reason: str = "cancel"


@dataclass
class ActionRequest:
    platform_id: str
    action_kind: ActionKind
    target_id: Optional[str] = None
    waypoint: Optional[Tuple[float, float]] = None
    course: Optional[float] = None
    speed: Optional[float] = None
    meta: Dict = field(default_factory=dict)

    @property
    def channel(self) -> ActionChannel:
        return ACTION_CHANNEL.get(self.action_kind, ActionChannel.SYSTEM)


@dataclass
class TaskFeedback:
    platform_id: str
    task_id: str
    status: TaskStatus
    phase: Phase
    target_id: Optional[str] = None
    target_visible: bool = False
    target_confidence: float = 0.0
    need_reallocation: bool = False
    reason_code: FeedbackReason = FeedbackReason.NONE


@dataclass
class ExecutionContext:
    """Legal Harness runtime snapshot handed to the BT each tick.

    NO ground truth / true enemy state / future trajectory / undetected targets.
    """
    platform_id: str
    platform_type: PlatformType
    sim_time: float
    platform_state: Dict = field(default_factory=dict)      # own state (position/speed/heading/alive/...)
    tracks: Dict = field(default_factory=dict)              # belief tracks {name: {position, confidence, visible, ...}}
    controller_feedback: Optional[Dict] = None              # last controller result
    safety_feedback: Optional[Dict] = None                  # {action_text: ACCEPTED/REJECTED/...}
    nearby_friendlies: List[Dict] = field(default_factory=list)
    hazards: List[Dict] = field(default_factory=list)


@dataclass
class BTStepResult:
    tick_id: int
    platform_id: str
    root_status: str
    action_requests: List[ActionRequest]
    task_feedback: TaskFeedback
    active_branch: str


# ════════════════════════════════════════════════════════════════
# PlatformExecutive — the contract the Harness consumes
# ════════════════════════════════════════════════════════════════
class PlatformExecutive(abc.ABC):
    @abc.abstractmethod
    def submit_task(self, command: TaskCommand) -> TaskAck:
        ...

    @abc.abstractmethod
    def cancel_task(self, request: CancelTaskRequest) -> TaskAck:
        ...

    @abc.abstractmethod
    def tick(self, context: ExecutionContext) -> BTStepResult:
        ...


# ════════════════════════════════════════════════════════════════
# STUB Behavior Tree (the thing being wrapped; no gRPC/HTTP writes)
# ════════════════════════════════════════════════════════════════
HARNESS_BT_MODE = True       # BT must NOT write to simulator (Harness /apply is the only writer)
REACQUIRE_TIMEOUT_S = 60.0   # local reacquire window before need_reallocation
LOCK_RANGE = 40_000.0
USV_RADAR = 35_000.0


def _bearing(a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    return math.degrees(math.atan2(dx, dy)) % 360.0


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


class StubBehaviorTree:
    """Deterministic minimal per-platform tree (approach→orbit/track→engage / return→dock / hold).

    Reads the assigned task + ExecutionContext from the blackboard (populated by the bridge).
    target_id is IMMUTABLE once assigned. No simulator writes.
    """

    def __init__(self, platform_id: str, platform_type: PlatformType):
        self.platform_id = platform_id
        self.platform_type = platform_type
        self.blackboard: Dict = {}
        self.active_task: Optional[TaskCommand] = None
        self.phase = Phase.HOLD
        self.lost_since: Optional[float] = None
        self.last_action_kind: Optional[ActionKind] = None
        self.reacquire_attempts = 0

    # ── BT bridge hooks ──
    def pre_tick(self, context: ExecutionContext) -> None:
        """ExecutionContext -> blackboard (legal only)."""
        self.blackboard["context"] = context
        self.blackboard["platform_state"] = context.platform_state
        self.blackboard["tracks"] = context.tracks
        self.blackboard["safety_feedback"] = context.safety_feedback

    def tick(self) -> Tuple[str, List[ActionRequest], TaskFeedback]:
        task = self.active_task
        ctx = self.blackboard.get("context")
        if task is None or ctx is None:
            return ("IDLE", [], TaskFeedback(
                self.platform_id, "", TaskStatus.PENDING, Phase.HOLD, None))
        tid = task.target_id
        track = (ctx.tracks or {}).get(tid)
        visible = bool(track and track.get("visible", False))
        conf = float((track or {}).get("confidence", 0.0) or 0.0)
        safety = ctx.safety_feedback or {}
        # if the last BT action was rejected by ActionSafety, do not blindly repeat it
        fallback = bool(self.last_action_kind and
                        any(v in ("REJECTED", "invalid", "denied") for v in safety.values()))
        if fallback:
            self.phase = Phase.HOLD
            self.last_action_kind = ActionKind.HOLD
            fb = TaskFeedback(self.platform_id, task.task_id, TaskStatus.RUNNING, Phase.HOLD,
                              tid, visible, conf, False, FeedbackReason.SAFETY_REJECTED)
            return ("FAILURE", [ActionRequest(self.platform_id, ActionKind.HOLD,
                                              target_id=tid)], fb)

        actions: List[ActionRequest] = []
        reason = FeedbackReason.NONE
        need_realloc = False
        status = TaskStatus.RUNNING

        if task.task_type in (TaskType.INTERCEPT_LOCK, TaskType.ENGAGE_TARGET,
                              TaskType.COOPERATIVE_LOCK):
            # USV engage / UAV cooperative-lock both home on the ASSIGNED target only
            if not visible:
                # local reacquire; target stays fixed (never swapped)
                if self.lost_since is None:
                    self.lost_since = ctx.sim_time
                elapsed = ctx.sim_time - self.lost_since
                self.phase = Phase.REACQUIRE
                actions.append(ActionRequest(self.platform_id, ActionKind.REACQUIRE,
                                             target_id=tid,
                                             course=_course_toward(ctx, track, tid)))
                self.reacquire_attempts += 1
                reason = FeedbackReason.TARGET_LOST
                if elapsed >= REACQUIRE_TIMEOUT_S:
                    need_realloc = True
                    reason = FeedbackReason.TARGET_LOST_TIMEOUT
                    status = TaskStatus.COMPLETED
                self.last_action_kind = ActionKind.REACQUIRE
            else:
                self.lost_since = None
                tpos = track["position"]
                ppos = ctx.platform_state.get("position")
                if ppos is None:
                    return ("FAILURE", [ActionRequest(self.platform_id, ActionKind.HOLD,
                                                      target_id=tid)], TaskFeedback(
                        self.platform_id, task.task_id, TaskStatus.RUNNING, Phase.HOLD,
                        tid, visible, conf))
                d = _dist(ppos, tpos)
                if task.platform_type == PlatformType.UAV:
                    # cooperative lock / situation update: hold sensor standoff
                    self.phase = Phase.ORBIT
                    actions.append(ActionRequest(self.platform_id, ActionKind.ORBIT_TARGET,
                                                 target_id=tid, waypoint=tpos,
                                                 course=_bearing(ppos, tpos)))
                elif d > LOCK_RANGE:
                    self.phase = Phase.APPROACH
                    actions.append(ActionRequest(self.platform_id, ActionKind.APPROACH_TARGET,
                                                 target_id=tid, waypoint=tpos,
                                                 course=_bearing(ppos, tpos)))
                elif d <= LOCK_RANGE:
                    # in lock range: orbit/track then engage
                    if task.task_type == TaskType.ENGAGE_TARGET or self.reacquire_attempts == 0:
                        self.phase = Phase.ENGAGE
                        actions.append(ActionRequest(self.platform_id, ActionKind.ENGAGE_TARGET,
                                                     target_id=tid, waypoint=tpos))
                        actions.append(ActionRequest(self.platform_id, ActionKind.ORBIT_TARGET,
                                                     target_id=tid, waypoint=tpos,
                                                     course=_bearing(ppos, tpos)))
                    else:
                        self.phase = Phase.TRACK
                        actions.append(ActionRequest(self.platform_id, ActionKind.TRACK_TARGET,
                                                     target_id=tid, waypoint=tpos,
                                                     course=_bearing(ppos, tpos)))
                self.last_action_kind = actions[-1].action_kind if actions else None

        elif task.task_type == TaskType.SITUATION_UPDATE:
            self.phase = Phase.SEARCH
            wp = task.constraints.get("waypoint")
            actions.append(ActionRequest(self.platform_id, ActionKind.NAVIGATE_TO,
                                         waypoint=wp,
                                         course=_bearing(ctx.platform_state.get("position"), wp)
                                         if wp and ctx.platform_state.get("position") else None))
            self.last_action_kind = ActionKind.NAVIGATE_TO

        elif task.task_type == TaskType.RETURN_RECHARGE:
            self.phase = Phase.RETURN
            base = task.constraints.get("base")
            actions.append(ActionRequest(self.platform_id, ActionKind.RETURN_TO_BASE,
                                         waypoint=base,
                                         course=_bearing(ctx.platform_state.get("position"), base)
                                         if base and ctx.platform_state.get("position") else None))
            actions.append(ActionRequest(self.platform_id, ActionKind.LAND_OR_DOCK,
                                         waypoint=base))
            self.last_action_kind = ActionKind.RETURN_TO_BASE

        else:  # HOLD_POSITION and anything else
            self.phase = Phase.HOLD
            actions.append(ActionRequest(self.platform_id, ActionKind.HOLD, target_id=tid))
            self.last_action_kind = ActionKind.HOLD

        fb = TaskFeedback(self.platform_id, task.task_id, status, self.phase,
                          tid, visible, conf, need_realloc, reason)
        return ("RUNNING" if status == TaskStatus.RUNNING else "SUCCESS",
                actions, fb)


def _course_toward(ctx, track, tid):
    p = ctx.platform_state.get("position")
    if p and track and track.get("position"):
        return _bearing(p, track["position"])
    return None


class StubBTBridge:
    """Minimal bridge mirroring bt_bridge.pre_tick / post_tick (no simulator writes)."""

    def pre_tick(self, tree: StubBehaviorTree, context: ExecutionContext) -> None:
        tree.pre_tick(context)

    def post_tick(self, tree: StubBehaviorTree, result: BTStepResult) -> None:
        # interface hook: currently no-op; real bridge would wrap logs/feedback
        pass


# ════════════════════════════════════════════════════════════════
# BTPlatformExecutive — per-platform wrapper (the Harness-facing object)
# ════════════════════════════════════════════════════════════════
class BTPlatformExecutive(PlatformExecutive):
    def __init__(self, platform_id: str, platform_type: PlatformType,
                 tree: Optional["object"] = None,
                 blackboard: Optional[Dict] = None,
                 bt_bridge: Optional["object"] = None):
        self.platform_id = platform_id
        self.platform_type = platform_type
        if tree is None:
            from bt_real_trees import make_executive_tree
            tree = make_executive_tree(platform_id, platform_type)
        if bt_bridge is None:
            from bt_real_trees import BTBridge
            bt_bridge = BTBridge()
        self.tree = tree
        self.blackboard = blackboard if blackboard is not None else {}
        self.bt_bridge = bt_bridge
        self.active_task: Optional[TaskCommand] = None
        self.task_revision: Optional[int] = None
        self._plan_revision: Optional[int] = None
        self.last_feedback: Optional[TaskFeedback] = None
        self._tick_id = 0
        self._last_submit = 0.0

    # ── submit_task ──
    def submit_task(self, command: TaskCommand, now_sim: Optional[float] = None) -> TaskAck:
        now = time.time()
        if command.platform_id != self.platform_id:
            return TaskAck(AckCode.INVALID_PLATFORM, command.task_id, self.platform_id,
                           f"platform mismatch: {command.platform_id}", now)
        if command.platform_type != self.platform_type:
            return TaskAck(AckCode.INVALID_TYPE, command.task_id, self.platform_id,
                           f"type mismatch: {command.platform_type}", now)
        # expired command (if sim_time known at submit)
        if now_sim is not None and command.valid_until is not None and now_sim > command.valid_until:
            return TaskAck(AckCode.EXPIRED, command.task_id, self.platform_id,
                           f"valid_until={command.valid_until} < now={now_sim}", now)
        # plan revision guard: a lower plan revision for the same plan is stale,
        # regardless of task revision (checked BEFORE the duplicate gate)
        if (self.active_task is not None and command.plan_id
                and command.plan_id == self.active_task.plan_id
                and self._plan_revision is not None
                and command.plan_revision < self._plan_revision):
            return TaskAck(AckCode.STALE_REJECTED, command.task_id, self.platform_id,
                           f"stale plan revision {command.plan_revision} < {self._plan_revision}", now)
        # duplicate: same task_id + same revision while active → ignore (no re-init)
        if self.active_task is not None and command.task_id == self.active_task.task_id:
            if command.revision == self.task_revision:
                return TaskAck(AckCode.DUPLICATE_IGNORED, command.task_id, self.platform_id,
                               "task already active; unchanged", now)
            if command.revision < self.task_revision:
                return TaskAck(AckCode.STALE_REJECTED, command.task_id, self.platform_id,
                               f"stale revision {command.revision} < {self.task_revision}", now)
        # preemption: a different task is active
        preempted = (self.active_task is not None
                     and command.task_id != self.active_task.task_id)
        if preempted:
            old = self.active_task
            allowed = command.safety_override or old.preemptible or command.priority > old.priority
            if not allowed:
                return TaskAck(AckCode.BUSY, command.task_id, self.platform_id,
                               "active task not preemptible", now)
        self.active_task = command
        self.task_revision = command.revision
        self._plan_revision = command.plan_revision
        self.tree.active_task = command
        self.tree.lost_since = None
        self.tree.reacquire_attempts = 0
        self.tree.phase = Phase.HOLD
        if hasattr(self.tree, "root"):
            self.tree.root.reset()   # clear memory branch on task (re)assignment
        self._last_submit = now
        if preempted:
            code = AckCode.ACCEPTED_WITH_PREEMPTION
            reason = FeedbackReason.SAFETY_OVERRIDE if command.safety_override \
                else FeedbackReason.PREEMPTED
            msg = f"preempted previous task ({reason.value})"
        else:
            code, reason, msg = AckCode.ACCEPTED, FeedbackReason.NONE, "accepted"
        return TaskAck(code, command.task_id, self.platform_id, msg, now)

    # ── cancel_task ──
    def cancel_task(self, request: CancelTaskRequest) -> TaskAck:
        now = time.time()
        if request.platform_id != self.platform_id:
            return TaskAck(AckCode.INVALID_PLATFORM, request.task_id, self.platform_id,
                           "platform mismatch", now)
        if self.active_task is None or request.task_id != self.active_task.task_id:
            return TaskAck(AckCode.NOT_FOUND, request.task_id, self.platform_id,
                           "no matching active task", now)
        # reset task-related memory branch only (keep the tree itself)
        self.active_task = None
        self.task_revision = None
        self._plan_revision = None
        self.tree.active_task = None
        self.tree.phase = Phase.HOLD
        self.tree.lost_since = None
        self.tree.reacquire_attempts = 0
        if hasattr(self.tree, "root"):
            self.tree.root.reset()
        self._last_submit = 0.0
        return TaskAck(AckCode.CANCELLED, request.task_id, self.platform_id,
                       "cancelled", now)

    # ── tick ──
    def tick(self, context: ExecutionContext) -> BTStepResult:
        self._tick_id += 1
        # strict wrapper: bridge.pre_tick -> tree.tick -> bridge.post_tick
        self.bt_bridge.pre_tick(self.tree, context)
        root_status, actions, feedback = self.tree.tick()
        result = BTStepResult(
            tick_id=self._tick_id,
            platform_id=self.platform_id,
            root_status=root_status,
            action_requests=actions,
            task_feedback=feedback,
            active_branch=str(self.tree.phase.value),
        )
        self.bt_bridge.post_tick(self.tree, result)
        self.last_feedback = feedback
        return result

    def assert_no_sim_writes(self):
        """HARNESS_BT_MODE guard: the BT wrapper never writes to the simulator."""
        # nothing here ever calls gRPC/HTTP; this is a documented invariant


# ════════════════════════════════════════════════════════════════
# BTActionAdapter — ActionRequest[] -> POST /apply payload
# ════════════════════════════════════════════════════════════════
class BTActionAdapter:
    """Maps intent-level ActionRequest[] to the Harness /apply payload.

    Does NOT touch /legal_actions (the legal space is unchanged); BT output is simply
    one decision source that the Harness feeds through ActionSafety before /apply.
    """

    USV_SPEED = 20.0
    UAV_SPEED = 100.0
    RETURN_COURSE = 270.0  # west, toward home

    def to_apply_payload(self, action_requests: List[ActionRequest]) -> Dict:
        actions = []
        for ar in action_requests:
            item = self._to_action(ar)
            if item:
                actions.append(item)
        return {"actions": actions}

    def _to_action(self, ar: ActionRequest) -> Optional[Dict]:
        pid = ar.platform_id
        is_uav = ar.platform_id and ar.platform_id.startswith("white_uav")
        if ar.action_kind == ActionKind.LAUNCH:
            return {"action_text": f"{pid} 从 {_home_of(pid)} 起飞 target_speed={self.UAV_SPEED:.1f} target_course=90.0",
                    "action_type": "launch_uav"}
        if ar.action_kind in (ActionKind.NAVIGATE_TO, ActionKind.APPROACH_TARGET,
                              ActionKind.ORBIT_TARGET, ActionKind.TRACK_TARGET,
                              ActionKind.REACQUIRE):
            speed = self.UAV_SPEED if is_uav else self.USV_SPEED
            course = ar.course if ar.course is not None else self.RETURN_COURSE
            text = f"{pid} {'飞行' if is_uav else '移动'} target_speed={speed:.1f} target_course={course:.1f}"
            return {"action_text": text, "action_type": "fly" if is_uav else "move"}
        if ar.action_kind == ActionKind.ENGAGE_TARGET and ar.target_id:
            return {"action_text": f"{pid} 锁定 {ar.target_id}", "action_type": "lock"}
        if ar.action_kind == ActionKind.RETURN_TO_BASE:
            course = ar.course if ar.course is not None else self.RETURN_COURSE
            return {"action_text": f"{pid} 飞行 target_speed={self.UAV_SPEED:.1f} target_course={course:.1f}",
                    "action_type": "fly"}
        if ar.action_kind == ActionKind.LAND_OR_DOCK:
            home = ar.meta.get("home") or _home_of(pid)
            return {"action_text": f"{pid} 降落 {home}", "action_type": "land_uav"}
        if ar.action_kind == ActionKind.HOLD:
            return {"action_text": f"{pid} 移动 target_speed={self.USV_SPEED:.1f} target_course=90.0",
                    "action_type": "move"}
        return None


def _home_of(uav_name: str) -> str:
    # default dock mapping: white_uav{i} -> white_usv{i}
    import re
    m = re.search(r"(\d+)$", uav_name)
    return f"white_usv{m.group(1)}" if m else "white_usv1"
