from fastapi import APIRouter, HTTPException
from typing import List
from pomdp_api.shared import (
    _state, _log, _ACTION_SCHEMAS, MACRO_STEP_DURATION,
    _fetch_raw_state, _build_legal_actions, _raise_on_state_error,
    _parse_action_text, _execute_one_action, _record_step,
    _finalize_game_log, _build_result, _r2,
    StateFetchError, ApplyRequest,
)

router = APIRouter()

@router.get("/legal_actions")
async def get_legal_actions():
    """合法动作空间：按当前仿真状态枚举此刻所有单位可执行的指令（按类型分组）。

    给大模型 Agent 做候选集；行为树自己生成动作，不经此端口。
    """
    if not _state.engine_name:
        raise HTTPException(status_code=404, detail="仿真未启动")
    try:
        raw = _fetch_raw_state()
    except StateFetchError as e:
        _raise_on_state_error(e)
    result = _build_legal_actions(raw)
    total = sum(len(v) for v in result["动作"].values()) if result.get("动作") else 0
    _log.info("GET /legal_actions → %d 个动作", total)
    return result

@router.post("/apply")
async def apply_actions(req: ApplyRequest):
    """执行动作列表并推进一个宏观步（默认 30 仿真秒）。

    请求体: {"actions": [{"action_text", "action_type"}]}。
    逐条判定合法性并下发后端；任一动作失败即整批返回 400
    （detail 含 [动作N] 失败序号，此前动作已在仿真中执行）。
    """
    global _state
    _log.info("POST /apply | %d 个动作", len(req.actions))
    if not _state.engine_name:
        raise HTTPException(status_code=404, detail="仿真未启动")
    if _state.ended:
        raise HTTPException(status_code=409, detail="当前 episode 已结束，请 POST /reset 开启新局")

    results: List[dict] = []
    skipped_msgs: List[str] = []

    for i, item in enumerate(req.actions):
        if item.action_type not in _ACTION_SCHEMAS:
            raise HTTPException(status_code=400,
                detail=f"[动作{i+1}] 未知动作类型 '{item.action_type}'，合法值: {list(_ACTION_SCHEMAS.keys())}")
        try:
            parsed = _parse_action_text(item.action_text, item.action_type)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"[动作{i+1}] {e}")
        # 必填参数已在 _parse_action_text 内校验（缺失会抛 ValueError）
        exec_result = _execute_one_action(parsed)
        results.append({
            "序号": i + 1, "动作": item.action_text.strip(),
            "成功": exec_result["ok"], "跳过": exec_result.get("skipped", False),
            "详情": exec_result["detail"],
        })
        if exec_result.get("skipped"):
            skipped_msgs.append(f"[动作{i+1}] {exec_result['detail']}")
        if not exec_result["ok"]:
            raise HTTPException(status_code=400, detail=f"[动作{i+1}] {exec_result['detail']}")

    for item in req.actions:
        _state.action_history.append(item.action_text.strip())

    try:
        raw = _fetch_raw_state()
        current_time = _r2(raw.get("time", 0))
        _state.release_until_time = current_time + MACRO_STEP_DURATION
        _record_step(raw, results, req.summary)
        if raw.get("ended", False) and not _state.ended:
            _state.ended = True
            _state.waiting_for_command = False
            result_info = _build_result(raw)
            _state.result = result_info["对局结果"]
            _finalize_game_log(raw)
    except StateFetchError:
        _state.release_until_time = (_state.release_until_time or 0) + MACRO_STEP_DURATION

    _state.waiting_for_command = False
    success_count = sum(1 for r in results if r["成功"] and not r["跳过"])
    skip_count = len(skipped_msgs)
    response = {
        "成功": True, "已队列": True, "执行结果": results,
        "执行统计": f"{len(results)} 个动作: {success_count} 成功, {skip_count} 跳过",
    }
    if skipped_msgs:
        response["跳过详情"] = skipped_msgs
    _log.info("apply 完成 | %s | release_until=%.1f", response["执行统计"], _state.release_until_time)
    return response
