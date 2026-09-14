"""树内工具与通用行为（两棵树共享）

工具：距离/方位/参数/目标航迹/动作发射/安全判定
通用行为：safety_hold / hold / 任务类型条件 / 目标可见条件
"""

import math
from typing import Any, Dict, List, Optional, Tuple

from .harness_interface import (
    ActionKind, ActionRequest, FeedbackReason, Phase, TaskType)
from .blackboard import Blackboard
from .status import Status, USV_PATROL_SPEED


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


def _own_course(bb: Blackboard) -> float:
    state = bb.get("ctx.platform_state") or {}
    try:
        return float(state.get("heading", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


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


def safety_hold_fn(bb: Blackboard, *, uav: bool) -> Status:
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


def hold_fn(bb: Blackboard, *, uav: bool) -> Status:
    """hold_fallback：待命/巡逻（USV 保持移动；UAV 悬停速度 0）"""
    if uav:
        _emit(bb, ActionKind.HOLD, course=_own_course(bb), speed=0.0,
              phase=Phase.hold, branch="hold")
    else:
        _emit(bb, ActionKind.HOLD, course=_own_course(bb),
              speed=_param(bb, "patrol_speed", USV_PATROL_SPEED),
              phase=Phase.hold, branch="hold")
    return Status.RUNNING


def task_type_is(bb: Blackboard, task_type: TaskType) -> Status:
    return (Status.SUCCESS
            if bb.get("task.task_type") == task_type else Status.FAILURE)


def target_visible(bb: Blackboard) -> Status:
    return (Status.SUCCESS if _target_track(bb) is not None
            else Status.FAILURE)
