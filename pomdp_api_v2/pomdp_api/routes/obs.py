from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from pomdp_api.shared import _state, _fetch_raw_state, _build_obs_text, _raise_on_state_error, StateFetchError

router = APIRouter()

@router.get("/obs", response_class=PlainTextResponse)
async def get_obs():
    """语义观察（纯文本）：把原始状态整理成 LLM 友好的人话描述。

    分段: [Info] / [我方无人艇] / [我方无人机] / [敌方情报] / [派生信号]。
    供大模型类 Agent 直接阅读；行为树 Agent 用 /raw（结构化）更高效。
    """
    if not _state.engine_name:
        raise HTTPException(status_code=404, detail="仿真未启动")
    try:
        raw = _fetch_raw_state()
    except StateFetchError as e:
        _raise_on_state_error(e)
    return _build_obs_text(raw)

@router.get("/raw")
async def get_raw():
    """原始仿真状态（结构化 JSON）：行为树 Agent 每步的决策依据。

    返回: time / white_usv_states / white_uav_states / white_observation 等。
    每次调用都从后端实时获取，不做缓存。
    """
    if not _state.engine_name:
        raise HTTPException(status_code=404, detail="仿真未启动")
    try:
        return _fetch_raw_state()
    except StateFetchError as e:
        _raise_on_state_error(e)
