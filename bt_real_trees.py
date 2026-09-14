#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""bt_real_trees.py — REAL (non-stub) per-platform behavior trees + bt_bridge.

Project has no pre-existing BT framework, so these are the real implementations of the
trees/contract the harness adapter consumes. The public Harness-facing interface
(PlatformExecutive / BTPlatformExecutive / BTActionAdapter) is NOT modified; only the
tree/bridge they wrap is real now (the earlier StubBehaviorTree/StubBTBridge remain for
pure-interface unit tests, not in the production path).

Real-tree guarantees (unchanged from the interface contract):
  - memory=True semantics: a RUNNING child keeps its slot across ticks.
  - SUCCESS / FAILURE / RUNNING statuses.
  - target_id is IMMUTABLE: it comes ONLY from the assigned TaskCommand; the tree has no
    internal allocator and never switches target (local reacquire keeps the same target;
    timeout -> need_reallocation=True).
  - HARNESS_BT_MODE: leaves emit intent-level ActionRequest[] into the blackboard ONLY.
    No gRPC / HTTP / simulator writes anywhere (network writer is Harness /apply).
  - Safety feedback: a REJECTED previous action makes the tree fall back to HOLD instead
    of blindly repeating the rejected primitive.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from bt_harness_interface import (  # noqa: E402
    ActionKind, ActionRequest, ExecutionContext, FeedbackReason, Phase, PlatformType,
    TaskFeedback, TaskStatus, TaskType,
)

LOCK_RANGE = 40_000.0
REACQUIRE_TIMEOUT_S = 60.0
USV_RADAR = 35_000.0


# ════════════════════════════════════════════════════════════════
# Minimal real behavior-tree framework (memory semantics, statuses)
# ════════════════════════════════════════════════════════════════
class Status:
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    RUNNING = "RUNNING"


class Node:
    def __init__(self, name: str, memory: bool = False):
        self.name = name
        self.children: List[Node] = []
        self.memory = memory
        self._running_child: Optional[Node] = None

    def add_child(self, child: "Node") -> "Node":
        self.children.append(child)
        return self

    def tick(self, bb: Dict) -> str:
        raise NotImplementedError

    def reset(self):
        self._running_child = None
        for c in self.children:
            c.reset()


class Behavior(Node):
    """Leaf: fn(bb) -> Status string."""

    def __init__(self, name: str, fn, memory: bool = False):
        super().__init__(name, memory)
        self.fn = fn

    def tick(self, bb: Dict) -> str:
        return self.fn(bb) or Status.RUNNING


class Sequence(Node):
    def tick(self, bb: Dict) -> str:
        start = 0
        if self.memory and self._running_child is not None:
            start = self.children.index(self._running_child)
        for i in range(start, len(self.children)):
            st = self.children[i].tick(bb)
            if st == Status.FAILURE:
                self._running_child = None
                return Status.FAILURE
            if st == Status.RUNNING:
                self._running_child = self.children[i]
                return Status.RUNNING
        self._running_child = None
        return Status.SUCCESS


class Selector(Node):
    def tick(self, bb: Dict) -> str:
        start = 0
        if self.memory and self._running_child is not None:
            start = self.children.index(self._running_child)
        for i in range(start, len(self.children)):
            st = self.children[i].tick(bb)
            if st != Status.FAILURE:
                self._running_child = self.children[i] if st == Status.RUNNING else None
                return st
        self._running_child = None
        return Status.FAILURE


class BehaviorTree:
    def __init__(self, root: Node, platform_id: str, platform_type: PlatformType):
        self.root = root
        self.platform_id = platform_id
        self.platform_type = platform_type
        self.blackboard: Dict = {}
        self.active_task = None   # set by BTPlatformExecutive.submit_task (target source)
        self.phase = Phase.HOLD
        self.reacquire_attempts = 0
        self.lost_since: Optional[float] = None
        self._reacquire_branch = False

    # ── bridge hook: ExecutionContext -> blackboard (legal only) ──
    def pre_tick(self, context: ExecutionContext) -> None:
        self.blackboard["context"] = context
        self.blackboard["platform_state"] = context.platform_state
        self.blackboard["tracks"] = context.tracks
        self.blackboard["safety_feedback"] = context.safety_feedback
        self.blackboard["action_requests"] = []
        self.blackboard["_feedback"] = None
        # target comes ONLY from the assigned TaskCommand (immutable)
        task = self.active_task
        self.blackboard["target_id"] = task.target_id if task else None
        self.blackboard["task_type"] = task.task_type if task else None
        self.blackboard["constraints"] = (task.constraints if task else {}) or {}

    def _emit(self, bb: Dict, ar: ActionRequest) -> None:
        bb["action_requests"].append(ar)

    def _feedback(self, bb: Dict, fb: TaskFeedback) -> None:
        bb["_feedback"] = fb

    def tick(self) -> Tuple[str, List[ActionRequest], Optional[TaskFeedback]]:
        if self.active_task is None:
            # no assigned task -> no actions (episode end / task cleared)
            fb = TaskFeedback(self.platform_id, "", TaskStatus.PENDING, Phase.HOLD, None)
            return "IDLE", [], fb
        task = self.active_task
        ctx = self.blackboard.get("context")
        now = ctx.sim_time if ctx else 0.0
        if task is not None:
            # not yet valid: do NOT execute early
            if task.valid_from is not None and now < task.valid_from:
                fb = TaskFeedback(self.platform_id, task.task_id, TaskStatus.PENDING, Phase.HOLD,
                                  task.target_id, reason_code=FeedbackReason.NOT_YET_VALID)
                return "SUCCESS", [], fb
            # expired: no further actions
            if task.valid_until is not None and now > task.valid_until:
                fb = TaskFeedback(self.platform_id, task.task_id, TaskStatus.COMPLETED, Phase.HOLD,
                                  task.target_id, need_reallocation=True,
                                  reason_code=FeedbackReason.EXPIRED)
                return "SUCCESS", [], fb
        status = self.root.tick(self.blackboard)
        actions = self.blackboard.get("action_requests", [])
        fb = self.blackboard.get("_feedback")
        if fb is None:
            fb = TaskFeedback(self.platform_id,
                              self.active_task.task_id if self.active_task else "",
                              TaskStatus.RUNNING, self.phase,
                              self.blackboard.get("target_id"))
        return status, actions, fb


# ════════════════════════════════════════════════════════════════
# Blackboard helpers (real-tree leaf logic; no allocator / no sim writes)
# ════════════════════════════════════════════════════════════════
def _pos(bb):
    return (bb.get("platform_state") or {}).get("position")


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _bearing(a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    return math.degrees(math.atan2(dx, dy)) % 360.0


def _safety_result(bb):
    """Return (blocked, reason) from ExecutionContext.safety_feedback.

    PASS / CLAMPED / MODIFIED -> not blocked (CLAMPED/MODIFIED are recorded, not failures).
    REJECTED / OVERRIDDEN       -> blocked (safety takeover).
    """
    safety = bb.get("safety_feedback") or {}
    for v in safety.values():
        if v == "REJECTED":
            return True, FeedbackReason.SAFETY_REJECTED
        if v == "OVERRIDDEN":
            return True, FeedbackReason.SAFETY_OVERRIDE
    return False, FeedbackReason.NONE


def _safety_blocked(bb) -> bool:
    blocked, _ = _safety_result(bb)
    return blocked


def _target(bb):
    tid = bb.get("target_id")
    return tid, (bb.get("tracks") or {}).get(tid)


# ── USV leaves ──
def usv_safety_hold(bb):
    blocked, reason = _safety_result(bb)
    if not blocked:
        return Status.FAILURE
    tree = bb.get("_tree")
    if tree:
        tree.phase = Phase.HOLD
    bb["_feedback"] = TaskFeedback(bb.get("_platform"), bb.get("_taskid") or "", TaskStatus.RUNNING,
                                   Phase.HOLD, bb.get("target_id"),
                                   reason_code=reason)
    bb["_tree"]._emit(bb, ActionRequest(bb.get("_platform"), ActionKind.HOLD,
                                        target_id=bb.get("target_id")))
    return Status.SUCCESS


def usv_approach(bb):
    tid, track = _target(bb)
    p = _pos(bb)
    if tid is None or track is None or not track.get("visible") or p is None:
        return Status.FAILURE
    d = _dist(p, track["position"])
    if d <= LOCK_RANGE:
        return Status.SUCCESS  # approach complete -> proceed to engage
    tree = bb.get("_tree")
    if tree:
        tree.phase = Phase.APPROACH
    bb["_tree"]._emit(bb, ActionRequest(bb.get("_platform"), ActionKind.APPROACH_TARGET,
                                        target_id=tid, waypoint=track["position"],
                                        course=_bearing(p, track["position"])))
    bb["_feedback"] = TaskFeedback(bb.get("_platform"), bb.get("_taskid") or "",
                                   TaskStatus.RUNNING, Phase.APPROACH, tid, True,
                                   float(track.get("confidence", 0.0) or 0.0))
    return Status.RUNNING


def usv_engage(bb):
    tid, track = _target(bb)
    p = _pos(bb)
    if tid is None or track is None or not track.get("visible") or p is None:
        return Status.FAILURE
    d = _dist(p, track["position"])
    if d > LOCK_RANGE:
        return Status.FAILURE
    tree = bb.get("_tree")
    pst = bb.get("platform_state") or {}
    already_locking = bool(pst.get("is_locking")) and pst.get("locking_unit") == tid
    if tree:
        tree.phase = Phase.ENGAGE
    if not already_locking:
        # lock acquisition (once); then standoff orbit to preserve the 300s window
        bb["_tree"]._emit(bb, ActionRequest(bb.get("_platform"), ActionKind.ENGAGE_TARGET,
                                            target_id=tid, waypoint=track["position"]))
    bb["_tree"]._emit(bb, ActionRequest(bb.get("_platform"), ActionKind.ORBIT_TARGET,
                                        target_id=tid, waypoint=track["position"],
                                        course=_bearing(p, track["position"])))
    bb["_feedback"] = TaskFeedback(bb.get("_platform"), bb.get("_taskid") or "", TaskStatus.RUNNING,
                             Phase.ENGAGE, tid, True,
                             float(track.get("confidence", 0.0) or 0.0))
    return Status.SUCCESS


def usv_reacquire(bb):
    tid, track = _target(bb)
    ctx = bb.get("context")
    if tid is None or (track is not None and track.get("visible")):
        return Status.FAILURE
    tree = bb.get("_tree")
    task = tree.active_task if tree else None
    allow_reacq = True
    max_search = REACQUIRE_TIMEOUT_S
    if task is not None:
        allow_reacq = task.allow_local_reacquire
        max_search = task.max_search_time
    if not allow_reacq:
        bb["_feedback"] = TaskFeedback(bb.get("_platform"), bb.get("_taskid") or "",
                                       TaskStatus.COMPLETED, Phase.REACQUIRE, tid, False, 0.0,
                                       need_reallocation=True,
                                       reason_code=FeedbackReason.BLOCKED)
        return Status.SUCCESS
    if tree:
        tree.phase = Phase.REACQUIRE
        if tree.lost_since is None:
            tree.lost_since = (ctx.sim_time if ctx else 0.0)
        elapsed = (ctx.sim_time - tree.lost_since) if ctx else 0.0
        tree.reacquire_attempts += 1
        p = _pos(bb)
        bb["_tree"]._emit(bb, ActionRequest(bb.get("_platform"), ActionKind.REACQUIRE,
                                            target_id=tid,
                                            course=_bearing(p, track["position"]) if p and track else None))
        if elapsed >= max_search:
            bb["_feedback"] = TaskFeedback(bb.get("_platform"), bb.get("_taskid") or "",
                                           TaskStatus.COMPLETED, Phase.REACQUIRE, tid, False, 0.0,
                                           need_reallocation=True,
                                           reason_code=FeedbackReason.TARGET_LOST_TIMEOUT)
            return Status.SUCCESS
        bb["_feedback"] = TaskFeedback(bb.get("_platform"), bb.get("_taskid") or "",
                                       TaskStatus.RUNNING, Phase.REACQUIRE, tid, False, 0.0,
                                       need_reallocation=False,
                                       reason_code=FeedbackReason.TARGET_LOST)
        return Status.RUNNING
    return Status.FAILURE


def usv_hold(bb):
    tree = bb.get("_tree")
    if tree:
        tree.phase = Phase.HOLD
    bb["_tree"]._emit(bb, ActionRequest(bb.get("_platform"), ActionKind.HOLD,
                                        target_id=bb.get("target_id")))
    bb["_feedback"] = TaskFeedback(bb.get("_platform"), bb.get("_taskid") or "", TaskStatus.RUNNING,
                             Phase.HOLD, bb.get("target_id"))
    return Status.SUCCESS


# ── UAV leaves ──
def _docked(bb):
    pst = bb.get("platform_state") or {}
    return bool(pst.get("is_at_usv", False))


def _maybe_launch(bb):
    """If the UAV is still on the ship, emit LAUNCH (launch sequence) and wait."""
    if not _docked(bb):
        return False
    tree = bb.get("_tree")
    if tree:
        tree.phase = Phase.DOCK
    bb["_tree"]._emit(bb, ActionRequest(bb.get("_platform"), ActionKind.LAUNCH))
    return True


def uav_coop_approach(bb):
    if _maybe_launch(bb):
        return Status.RUNNING
    tid, track = _target(bb)
    p = _pos(bb)
    if tid is None or track is None or not track.get("visible") or p is None:
        return Status.FAILURE
    d = _dist(p, track["position"])
    if d <= USV_RADAR:   # within cooperative-lock sensor standoff -> orbit
        return Status.SUCCESS
    tree = bb.get("_tree")
    if tree:
        tree.phase = Phase.APPROACH
    bb["_tree"]._emit(bb, ActionRequest(bb.get("_platform"), ActionKind.APPROACH_TARGET,
                                        target_id=tid, waypoint=track["position"],
                                        course=_bearing(p, track["position"])))
    return Status.RUNNING


def uav_coop_orbit(bb):
    tid, track = _target(bb)
    p = _pos(bb)
    if tid is None or track is None or not track.get("visible") or p is None:
        return Status.FAILURE
    tree = bb.get("_tree")
    if tree:
        tree.phase = Phase.ORBIT
    bb["_tree"]._emit(bb, ActionRequest(bb.get("_platform"), ActionKind.ORBIT_TARGET,
                                        target_id=tid, waypoint=track["position"],
                                        course=_bearing(p, track["position"])))
    bb["_feedback"] = TaskFeedback(bb.get("_platform"), bb.get("_taskid") or "", TaskStatus.RUNNING,
                             Phase.ORBIT, tid, True, float(track.get("confidence", 0.0) or 0.0))
    return Status.SUCCESS


def uav_navigate(bb):
    if _maybe_launch(bb):
        return Status.RUNNING
    wp = bb.get("constraints", {}).get("waypoint")
    p = _pos(bb)
    tree = bb.get("_tree")
    if tree:
        tree.phase = Phase.SEARCH
    bb["_tree"]._emit(bb, ActionRequest(bb.get("_platform"), ActionKind.NAVIGATE_TO,
                                        waypoint=wp,
                                        course=_bearing(p, wp) if wp and p else None))
    bb["_feedback"] = TaskFeedback(bb.get("_platform"), bb.get("_taskid") or "", TaskStatus.RUNNING,
                             Phase.SEARCH, bb.get("target_id"))
    return Status.RUNNING


def uav_return(bb):
    base = bb.get("constraints", {}).get("base")
    p = _pos(bb)
    tree = bb.get("_tree")
    if tree:
        tree.phase = Phase.RETURN
    bb["_tree"]._emit(bb, ActionRequest(bb.get("_platform"), ActionKind.RETURN_TO_BASE,
                                        waypoint=base,
                                        course=_bearing(p, base) if base and p else 270.0))
    return Status.SUCCESS


def uav_dock(bb):
    tree = bb.get("_tree")
    if tree:
        tree.phase = Phase.DOCK
    bb["_tree"]._emit(bb, ActionRequest(bb.get("_platform"), ActionKind.LAND_OR_DOCK,
                                        waypoint=bb.get("constraints", {}).get("base"),
                                        meta={"home": bb.get("constraints", {}).get("base") or _home(bb)}))
    bb["_feedback"] = TaskFeedback(bb.get("_platform"), bb.get("_taskid") or "", TaskStatus.COMPLETED,
                             Phase.DOCK, bb.get("target_id"))
    return Status.SUCCESS


def _home(bb):
    import re
    m = re.search(r"(\d+)$", bb.get("_platform") or "")
    return f"white_usv{m.group(1)}" if m else "white_usv1"


# ════════════════════════════════════════════════════════════════
# Tree construction (per platform; target/task ONLY from TaskCommand)
# ════════════════════════════════════════════════════════════════
def build_usv_tree(platform_id: str) -> BehaviorTree:
    def cond_visible(bb):
        tid, track = _target(bb)
        return Status.SUCCESS if (tid and track and track.get("visible")) else Status.FAILURE

    # root Selector is NON-memory so the safety guard re-evaluates every tick;
    # memory lives on the sub-branches (approach/engage, reacquire).
    root = Selector("usv_root", memory=False)
    root.add_child(Behavior("safety_hold", usv_safety_hold))
    # approach-orbit-engage chain (memory): runs until in lock range then engages
    engage_seq = Sequence("engage_seq", memory=True)
    engage_seq.add_child(Behavior("approach", usv_approach))
    engage_seq.add_child(Behavior("engage", usv_engage))
    engage_guard = Selector("engage_or_hold", memory=True)
    engage_guard.add_child(engage_seq)
    engage_guard.add_child(Behavior("hold", usv_hold))
    visible_seq = Sequence("visible_guard", memory=False)
    visible_seq.add_child(Behavior("cond_visible", cond_visible))
    visible_seq.add_child(engage_guard)
    root.add_child(visible_seq)
    # lost -> reacquire (memory); timeout -> need_reallocation
    root.add_child(Behavior("reacquire", usv_reacquire, memory=True))
    root.add_child(Behavior("hold_fallback", usv_hold))

    tree = BehaviorTree(root, platform_id, PlatformType.USV)
    return tree


def build_uav_tree(platform_id: str) -> BehaviorTree:
    def cond_coop(bb):
        tt = bb.get("task_type")
        return Status.SUCCESS if tt in (TaskType.COOPERATIVE_LOCK,) else Status.FAILURE

    def cond_situ(bb):
        tt = bb.get("task_type")
        return Status.SUCCESS if tt in (TaskType.SITUATION_UPDATE,) else Status.FAILURE

    def cond_return(bb):
        tt = bb.get("task_type")
        return Status.SUCCESS if tt in (TaskType.RETURN_RECHARGE,) else Status.FAILURE

    root = Selector("uav_root", memory=False)
    root.add_child(Behavior("safety_hold", usv_safety_hold))
    # cooperative lock: approach -> orbit
    coop = Sequence("coop_seq", memory=True)
    coop.add_child(Behavior("cond_coop", cond_coop))
    coop.add_child(Behavior("coop_approach", uav_coop_approach))
    coop.add_child(Behavior("coop_orbit", uav_coop_orbit))
    root.add_child(coop)
    # situation update: navigate search
    situ = Sequence("situ_seq", memory=True)
    situ.add_child(Behavior("cond_situ", cond_situ))
    situ.add_child(Behavior("navigate", uav_navigate))
    root.add_child(situ)
    # return -> dock
    ret = Sequence("ret_seq", memory=True)
    ret.add_child(Behavior("cond_return", cond_return))
    ret.add_child(Behavior("return", uav_return))
    ret.add_child(Behavior("dock", uav_dock))
    root.add_child(ret)
    root.add_child(Behavior("hold_fallback", usv_hold))

    tree = BehaviorTree(root, platform_id, PlatformType.UAV)
    return tree


# ════════════════════════════════════════════════════════════════
# REAL bt_bridge (network responsibilities = 0)
# ════════════════════════════════════════════════════════════════
class BTBridge:
    """pre_tick: ExecutionContext -> Blackboard.  post_tick: Blackboard -> BTStepResult.
    No network / simulator writes anywhere.
    """

    def pre_tick(self, tree: BehaviorTree, context: ExecutionContext) -> None:
        tree.blackboard["_tree"] = tree
        tree.blackboard["_platform"] = tree.platform_id
        tree.blackboard["_taskid"] = tree.active_task.task_id if tree.active_task else ""
        tree.pre_tick(context)

    def post_tick(self, tree: BehaviorTree, result) -> None:
        # Blackboard already holds action_requests / feedback; nothing to send.
        pass


def make_executive_tree(platform_id: str, platform_type: PlatformType) -> BehaviorTree:
    """Factory used by BTPlatformExecutive for the REAL per-platform tree."""
    if platform_type == PlatformType.UAV:
        return build_uav_tree(platform_id)
    return build_usv_tree(platform_id)
