from fastapi import APIRouter, HTTPException
from pomdp_api.shared import _state, _fetch_raw_state, _build_result, StateFetchError
import pomdp_api.shared as shared

router = APIRouter()

@router.get("/result")
async def get_result():
    """对局结果分析：输赢判断 + 存活统计 + 敌方统计 + 奖励信号 + 行动历史。"""
    if not _state.engine_name and not _state.ended:
        raise HTTPException(status_code=404, detail="仿真未启动")
    try:
        raw = _fetch_raw_state()
    except StateFetchError as e:
        if e.error_type == "ENGINE_IS_NONE" and _state.ended:
            return {
                "对局结果": _state.result or "Result.Tie", "结果说明": "仿真引擎已停止",
                "行动总数": len(_state.action_history), "行动历史": _state.action_history,
            }
        elif e.error_type == "GRPC_ERROR":
            raise HTTPException(status_code=500, detail=e.message)
        else:
            raise HTTPException(status_code=500, detail=e.message)
    result = _build_result(raw)
    result["行动历史"] = _state.action_history
    return result

@router.get("/game_log")
async def get_game_log():
    """对局日志：每步的动作与结果、单位状态、雷达捕获、被动告警、奖励、事件。

    调用即把当前日志快照落盘到仓库根目录 logs/games/（步数有新增才写），
    对局封存（stop/reset/对局结束）时另有两份：每局完整 JSON +
    追加进合并格式文本日志 game_records.log。
    """
    # 注意: 必须经模块引用 shared._game_log（模块属性会在开新局时被重新绑定），
    # 直接 from-import 会持有初始 None 的旧引用 → 永远 404。
    if shared._game_log is None:
        raise HTTPException(status_code=404, detail="暂无对局日志，请先 POST /start 或 /reset")
    snap = shared._snapshot_game_log()
    return {
        "当前对局": shared._game_log.to_dict(),
        "快照文件": snap or "无新增步数，未重复写盘",
        "说明": "每步记录含: 动作与结果 | USV状态 | UAV状态 | 雷达捕获 | 被动告警 | 奖励 | 事件",
        "日志文件": [
            "合并格式(人/LLM阅读): 仓库根目录 logs/games/game_records.log"
            "（每局 episode=N 起、RESET 分割，外层数据与结果 + 内嵌单位动作块）",
            f"每局详细JSON: 仓库根目录 logs/games/game_{shared._game_log.episode_id}_*.json",
        ],
    }
