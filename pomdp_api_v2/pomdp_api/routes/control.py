from fastapi import APIRouter, HTTPException
from datetime import datetime
from pomdp_api.shared import (
    _state, _log,
    DEFAULT_SCRIPT,
    _known_scripts,
    _grpc_call, _do_init, _calibrate_epoch, _init_game_log,
    _reset_episode_state, _stop_episode_state, _save_game_log,
)

router = APIRouter()

def _check_script_name(script_name: str) -> None:
    """校验脚本名在当前后端可用列表中（未知脚本返回 400）"""
    if script_name not in _known_scripts():
        raise HTTPException(status_code=400,
            detail=f"未知脚本 '{script_name}'，可用: {_known_scripts()}")

@router.post("/start")
async def start(script_name: str = DEFAULT_SCRIPT):
    """启动仿真对局（?script_name= 选脚本/方案，默认"测试用例1"）。

    与 GET /stop 成对：每次 start 开新一局，对局编号递增、行动历史清空。
    已有对局在跑时返回 409（先 GET /stop）；要重开同一局请用 POST /reset。
    """
    global _state
    _log.info("POST /start | script=%s", script_name)
    _check_script_name(script_name)
    if _state.engine_name and _state.started:
        # 仅对局确实在跑时才 409；stop 后（started=False）直接走 _do_init 开新局
        try:
            check = _grpc_call("get_state")
            if check.msg == "FUNC_SUCCESS":
                raise HTTPException(status_code=409,
                    detail="仿真已在运行中，请先 GET /stop 或使用 POST /reset")
        except HTTPException:
            raise
        except Exception as e:
            _log.warning("start 前检查状态异常: %s", e)
            _state.engine_name = ""
    engine_name = _do_init(script_name)
    _state.engine_name = engine_name
    _state.episode_id += 1; _state.started = True; _state.ended = False
    _state.script_name = script_name
    _state.result = None; _state.waiting_for_command = True
    _state.release_until_time = None
    _state.start_real_time = datetime.now()
    _state.action_history.clear()
    _init_game_log(script_name)
    _calibrate_epoch()
    _log.info("启动成功 | episode=%d | engine=%s", _state.episode_id, _state.engine_name)
    return {
        "成功": True, "说明": f"仿真已启动，第 {_state.episode_id} 局",
        "对局编号": _state.episode_id, "已启动": True, "已结束": False,
        "等待指令": True, "脚本": script_name, "引擎": _state.engine_name,
    }

@router.get("/stop")
async def stop():
    """停止当前仿真（保留行动历史与对局日志），引擎释放。

    与 POST /start 成对：stop 后可直接 /start 开新一局（对局编号递增）。
    """
    global _state
    was_started = _state.started
    if not _state.engine_name:
        raise HTTPException(status_code=404, detail="仿真未启动，无需停止")
    try:
        _grpc_call("terminate", kwargs={}, engine_name="")
    except Exception as e:
        _log.warning("stop 释放引擎失败（继续标记停止）: %s", e)
    _state.engine_name = ""   # 引擎已释放，/start 可直接开新局
    _stop_episode_state()
    _save_game_log(closed_by="对局停止")  # 未结束就停的对局也封存，避免数据丢失
    return {
        "成功": True, "说明": "仿真已停止，行动历史已保留，可 POST /start 开新一局",
        "对局编号": _state.episode_id, "已启动": False, "已结束": True,
        "曾启动": was_started, "行动总数": len(_state.action_history),
    }

@router.post("/reset")
async def reset(script_name: str = DEFAULT_SCRIPT):
    """重置所有东西：终止旧引擎 → 重建新引擎 → 一切回到初始状态。

    - 引擎: 旧引擎终止、按 script_name 重新初始化（新 engine_name）
    - 对局: 编号归 1、已结束=False、结果=None、等待指令=True、开局时间刷新
    - 数据: 行动历史清空、对局日志全新（旧对局日志封存到 logs/games/ 留档）
    - 新开一局的推荐入口（/start 在有对局时会 409，本接口无条件重开）
    - 方案选择: script_name 参数，如后端已配置方案条目，可直接传方案名
    """
    global _state
    _log.info("POST /reset | script=%s", script_name)
    _check_script_name(script_name)
    _reset_episode_state()
    try:
        engine_name = _do_init(script_name)
        _state.engine_name = engine_name
        _state.episode_id = 1; _state.started = True; _state.ended = False
        _state.script_name = script_name
        _state.result = None; _state.waiting_for_command = True
        _state.release_until_time = None
        _state.start_real_time = datetime.now()
        _state.action_history.clear()
        _init_game_log(script_name)
        _calibrate_epoch()
        _log.info("重置成功 | episode=%d | engine=%s", _state.episode_id, _state.engine_name)
        return {"成功": True, "说明": "Reset", "已重置": True, "对局编号": 1,
                "已启动": True, "已结束": False, "等待指令": True, "脚本": script_name}
    except Exception as e:
        _log.error("重置失败: %s", e)
        raise HTTPException(status_code=500, detail=f"仿真启动失败: {e}")
