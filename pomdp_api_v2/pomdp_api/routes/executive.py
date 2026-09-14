"""行为树 Harness 端口 — 任务下发/取消与行为树动作输出

按《BT_HARNESS_INTERFACE_REFERENCE.md》接入（HARNESS_BT_MODE）：
Harness 经本端口驱动行为树，动作输出整批 POST /apply 执行（只有
Harness 一个 writer），再把 /apply 回执按动作文本传回驱动树状态推进。

  POST /bt/task         下发任务（§2.1 TaskCommand，含 revision/priority/
                        preemptible/safety_override 等幂等与抢占字段）
  POST /bt/task/cancel  取消任务（§2.3）
  GET  /bt/tasks        当前各平台登记任务列表
  POST /bt/actions      行为树决策动作输出（体可选: 上一步 /apply 回执）

决策权边界: Harness 拥有 WHO+WHAT（platform/target/task_type/role/约束），
行为树拥有 HOW/NEXT PHASE；target_id 指派后不可变。
"""

from dataclasses import asdict
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from pomdp_api.shared import (_log, _state, _fetch_raw_state,
                              _raise_on_state_error, StateFetchError)
from behavior_tree.harness_interface import (
    AckCode, BTActionAdapter, BTPlatformExecutive, CancelTaskRequest,
    ExecutionContext, PlatformType, TaskAck, TaskCommand, TaskFeedback,
    TaskType)

router = APIRouter(prefix="/bt", tags=["行为树"])


# ═══════════════════════════════════════════════════════════════
# 请求模型（§2 字段）
# ═══════════════════════════════════════════════════════════════

class TaskSubmitModel(BaseModel):
    task_id: str
    platform_id: str
    platform_type: str              # "USV" | "UAV"
    task_type: str                  # 见 TaskType
    target_id: Optional[str] = None
    role: str = "default"
    revision: int = 1
    priority: int = 0
    plan_id: str = ""
    plan_revision: int = 1
    valid_from: Optional[float] = None
    valid_until: Optional[float] = None
    preemptible: bool = True
    safety_override: bool = False
    allow_local_reacquire: bool = True
    max_search_time: float = 60.0
    constraints: dict = {}


class TaskCancelModel(BaseModel):
    platform_id: str
    task_id: str
    reason: str = "cancel"


class ApplyResultModel(BaseModel):
    """上一步 /apply 的单条动作回执（按动作文本关联行为树动作）"""
    动作: str
    成功: bool = True
    跳过: bool = False


class BTActionsBody(BaseModel):
    """可选体: 上一步 /bt/actions 输出的动作经 /apply 执行后的回执"""
    apply_results: List[ApplyResultModel] = []


# ─── 模块级执行器注册表（跨请求保持任务与树状态，随对局重置）──

_executives: Dict[str, BTPlatformExecutive] = {}
_uav_homes: Dict[str, str] = {}      # UAV 母舰记忆（飞行中引擎 home_name 为空）
_episode_key = None                  # (episode_id, engine_name) — 变化即对局重开


def _sync_episode() -> None:
    global _episode_key
    key = (_state.episode_id, _state.engine_name)
    if key != _episode_key:
        for ex in _executives.values():
            ex.reset()
        _executives.clear()
        _uav_homes.clear()
        _episode_key = key


def _executive(platform_id: str, platform_type: str) -> BTPlatformExecutive:
    """惰性创建/复用平台执行器（一个平台一个实例，包装一颗真实树）"""
    if platform_id not in _executives:
        _executives[platform_id] = BTPlatformExecutive(
            platform_id, PlatformType(platform_type))
    return _executives[platform_id]


def _enum_or_400(model, field: str, enum_cls):
    """字符串 → 枚举，非法值 400"""
    value = getattr(model, field)
    try:
        return enum_cls(value)
    except ValueError:
        raise HTTPException(status_code=400,
                            detail=f"非法 {field} '{value}'，合法值: "
                                   f"{[e.value for e in enum_cls]}")


def _now_sim_or_none() -> Optional[float]:
    """当前仿真秒（引擎未启动时为 None，跳过 expired 判定）"""
    if not _state.engine_name:
        return None
    try:
        raw = _fetch_raw_state()
    except StateFetchError:
        return None
    return float(raw.get("time", 0) or 0)


def _ack_dict(ack) -> dict:
    return {"受理": ack.code.value, "平台": ack.platform_id,
            "任务编号": ack.task_id, "消息": ack.message,
            "时间戳": ack.timestamp}


def _task_dict(cmd: TaskCommand) -> dict:
    return {"task_id": cmd.task_id, "platform_id": cmd.platform_id,
            "platform_type": cmd.platform_type.value,
            "task_type": cmd.task_type.value, "target_id": cmd.target_id,
            "role": cmd.role, "revision": cmd.revision,
            "priority": cmd.priority, "plan_id": cmd.plan_id,
            "plan_revision": cmd.plan_revision,
            "valid_from": cmd.valid_from, "valid_until": cmd.valid_until,
            "preemptible": cmd.preemptible,
            "safety_override": cmd.safety_override,
            "status": getattr(cmd, "status", None).value
            if getattr(cmd, "status", None) else None,
            "constraints": cmd.constraints}


def _feedback_dict(fb: TaskFeedback) -> dict:
    return {"platform_id": fb.platform_id, "task_id": fb.task_id,
            "status": fb.status.value, "phase": fb.phase,
            "target_id": fb.target_id, "target_visible": fb.target_visible,
            "target_confidence": fb.target_confidence,
            "need_reallocation": fb.need_reallocation,
            "reason_code": fb.reason_code.value}


# ═══════════════════════════════════════════════════════════════
# 端点
# ═══════════════════════════════════════════════════════════════

@router.post("/task")
async def submit_task(req: TaskSubmitModel):
    """下发平台任务（§2.1 + §4 生命周期语义）

    任务持久化: 只要 task_type/target/role/主要约束未变，不要每 tick 重发
    submit；只需反复 POST /bt/actions。只有 target 变化/任务变化/显式重分配/
    revision 更新/抢占才重新 submit。"""
    _sync_episode()
    command = TaskCommand(
        task_id=req.task_id, platform_id=req.platform_id,
        platform_type=_enum_or_400(req, "platform_type", PlatformType),
        task_type=_enum_or_400(req, "task_type", TaskType),
        target_id=req.target_id, role=req.role, revision=req.revision,
        priority=req.priority, plan_id=req.plan_id,
        plan_revision=req.plan_revision,
        valid_from=req.valid_from, valid_until=req.valid_until,
        preemptible=req.preemptible, safety_override=req.safety_override,
        allow_local_reacquire=req.allow_local_reacquire,
        max_search_time=req.max_search_time, constraints=req.constraints)
    ack = _executive(req.platform_id, req.platform_type
                     ).submit_task(command, _now_sim_or_none())
    _log.info("POST /bt/task | %s/%s %s %s → %s", req.plan_id, req.task_id,
              req.platform_id, req.task_type, ack.code.value)
    return _ack_dict(ack)


@router.post("/task/cancel")
async def cancel_task(req: TaskCancelModel):
    """取消任务（重置该任务相关 memory 分支，不销毁树）"""
    _sync_episode()
    ex = _executives.get(req.platform_id)
    if ex is None:
        return _ack_dict(TaskAck(code=AckCode.NOT_FOUND,
                                 task_id=req.task_id,
                                 platform_id=req.platform_id,
                                 message="平台无登记任务"))
    ack = ex.cancel_task(
        CancelTaskRequest(platform_id=req.platform_id, task_id=req.task_id,
                          reason=req.reason))
    _log.info("POST /bt/task/cancel | %s %s → %s", req.task_id,
              req.platform_id, ack.code.value)
    return _ack_dict(ack)


@router.get("/tasks")
async def list_tasks():
    """当前各平台登记任务列表"""
    _sync_episode()
    tasks = []
    for ex in _executives.values():
        for _, cmd in ex.active_tasks():
            tasks.append(_task_dict(cmd))
    return {"任务": tasks}


@router.post("/actions")
async def bt_actions(body: Optional[BTActionsBody] = None):
    """行为树决策动作输出（每平台一次 tick）— 有限的已决策动作集

    输出为 BT 已决策的具体动作（action_text/action_type，数值全部来自
    任务约束与树内计算，端口无预设值），是 /legal_actions 全量空间的
    有限子集：可整批 POST /apply 执行（/apply 推进一个宏观步），
    再将 /apply 执行结果（执行结果[].动作/成功/跳过）经本端口体传回，
    作为下一 tick 的 safety_feedback / controller_feedback 驱动树推进。"""
    _sync_episode()
    if not _state.engine_name:
        raise HTTPException(status_code=404, detail="仿真未启动")
    try:
        raw = _fetch_raw_state()
    except StateFetchError as e:
        _raise_on_state_error(e)

    body = body or BTActionsBody()
    # §9: safety_feedback = {动作文本: 跳过→REJECTED，否则 ACCEPTED}
    safety = {r.动作: ("REJECTED" if r.跳过 else "ACCEPTED")
              for r in body.apply_results}
    controller = {r.动作: {"ok": r.成功, "skipped": r.跳过}
                  for r in body.apply_results}

    contexts = _build_contexts(raw, safety, controller)

    adapter = BTActionAdapter()
    actions: List[dict] = []
    feedbacks: List[dict] = []
    platforms: Dict[str, dict] = {}
    max_tick = 0
    for pid, ex in list(_executives.items()):
        if ex.active_task is None:
            continue
        ctx = contexts.get(pid)
        if ctx is None or not ctx.platform_state.get("is_alive"):
            continue                      # 单位已摧毁/不在场：本 tick 跳过
        result = ex.tick(ctx)
        max_tick = max(max_tick, result.tick_id)
        platforms[pid] = {"root_status": result.root_status,
                          "active_branch": result.active_branch,
                          "动作数": len(result.action_requests)}
        if result.task_feedback:
            feedbacks.append(_feedback_dict(result.task_feedback))
        for r in result.action_requests:
            item = adapter.to_action_item(r)
            if item is not None:          # 数值缺失的动作不产出（无预设值）
                actions.append(item)

    notes = ["行为树决策动作，数值来自任务约束与树内计算（无预设值），"
             "可整批 POST /apply 执行，执行回执下次经本端口体传入"]
    if not actions and not feedbacks:
        notes.append("当前无活动任务：先 POST /bt/task 下发任务")
    elif not actions:
        notes.append("本步无产出动作（数值缺失或任务终态）")
    _log.info("POST /bt/actions | %d 个动作, %d 个任务反馈, %d 个平台",
              len(actions), len(feedbacks), len(platforms))
    return {"成功": True, "tick": max_tick, "动作": actions,
            "任务反馈": feedbacks, "平台": platforms, "说明": notes}


# ═══════════════════════════════════════════════════════════════
# ExecutionContext 构建（合法 runtime 快照，不含任何 ground truth）
# ═══════════════════════════════════════════════════════════════

def _build_contexts(raw: dict, safety: Dict[str, str],
                    controller: Dict[str, dict]) -> Dict[str, ExecutionContext]:
    """原始状态 → 各平台 ExecutionContext（§2.4 合法约束）

    tracks = 雷达捕获敌方（is_ship=False）+ 友方舰船（is_ship=True，
    供 UAV 返航找母舰）；仅合法观测，无 hidden_enemy/undetected 真值。
    """
    sim_time = float(raw.get("time", 0) or 0)
    usvs = raw.get("white_usv_states", [])
    uavs = raw.get("white_uav_states", [])

    ships: Dict[str, dict] = {}
    for u in usvs:
        if u.get("is_alive"):
            ships[u["name"]] = {"position": u.get("position"),
                                "visible": True, "confidence": 1.0,
                                "is_ship": True}

    tracks = dict(ships)
    for e in raw.get("white_observation", []):
        tracks[e.get("name", "?")] = {"position": e.get("position"),
                                      "visible": True, "confidence": 1.0,
                                      "is_ship": False}

    def _safety_for(pid: str) -> Dict[str, str]:
        return {k: v for k, v in safety.items() if k.startswith(f"{pid} ")}

    contexts: Dict[str, ExecutionContext] = {}
    friendlies = [{"name": n, "position": s["position"]}
                  for n, s in ships.items()]

    for u in usvs:
        name = u.get("name", "")
        if not name:
            continue
        contexts[name] = ExecutionContext(
            platform_id=name, platform_type=PlatformType.USV,
            sim_time=sim_time,
            platform_state={
                "position": u.get("position"),
                "speed": u.get("speed", 0),
                "heading": u.get("course", 0),
                "is_alive": u.get("is_alive", False),
                "is_locking": u.get("is_locking", False),
                "locking_unit": u.get("locking_unit", ""),
            },
            tracks=tracks, safety_feedback=_safety_for(name),
            controller_feedback=controller,
            nearby_friendlies=[f for f in friendlies if f["name"] != name])

    for u in uavs:
        name = u.get("name", "")
        if not name:
            continue
        home = u.get("home_name") or ""
        if home:
            _uav_homes[name] = home      # 停靠时记下母舰，飞行中沿用
        else:
            home = _uav_homes.get(name, "")
        contexts[name] = ExecutionContext(
            platform_id=name, platform_type=PlatformType.UAV,
            sim_time=sim_time,
            platform_state={
                "position": u.get("position"),
                "speed": u.get("speed", 0),
                "heading": u.get("course", 0),
                "is_alive": u.get("is_alive", False),
                "is_at_usv": u.get("is_at_usv", False),
                "home_name": home,
            },
            tracks=tracks, safety_feedback=_safety_for(name),
            controller_feedback=controller,
            nearby_friendlies=friendlies)

    return contexts
