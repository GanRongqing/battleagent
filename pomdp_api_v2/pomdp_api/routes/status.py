from fastapi import APIRouter, HTTPException

from pomdp_api.shared import (
    _state, _log, _HOST, _PORT, _API_HOST, APP_PORT,
    MACRO_STEP_DURATION, DEFAULT_SCRIPT,
    _fetch_script_list, _known_scripts,
    _fetch_raw_state, _build_enemy_intel, _raise_on_state_error,
    _grpc_call, _r2, _fmt_time, StateFetchError,
)

router = APIRouter()

@router.get("/")
async def index():
    """服务信息页：端点清单、决策循环说明、当前对局状态与配置。"""
    return {
        "服务": "仿真 POMDP API", "版本": "1.0",
        "说明": "军事仿真推演系统 POMDP 语义交互接口",
        "决策循环": [
            "GET  /status        → 检查 已结束 / 等待指令",
            "GET  /obs            → 获取语义观察（Plain Text）",
            "GET  /legal_actions  → 获取合法动作空间",
            "POST /apply          → 注入动作，推进一个宏观步",
            "重复直到 已结束=true",
        ],
        "端点": {
            "GET  /": "本页面", "GET  /health": "健康检测",
            "GET  /scripts": "可用仿真脚本列表",
            "POST /start": "启动仿真", "GET /stop": "停止仿真",
            "POST /reset": "重置仿真", "GET  /status": "全局状态同步",
            "GET  /obs": "语义观察", "GET  /legal_actions": "合法动作空间",
            "POST /apply": "注入动作列表", "GET  /result": "对局结果分析",
            "GET  /game_log": "对局日志",
        },
        "配置": {
            "仿真后端": f"{_HOST}:{_PORT}",
            "宏观步步长": f"{MACRO_STEP_DURATION}s（仿真秒数）",
        },
        "当前状态": {
            "已启动": _state.started, "已结束": _state.ended,
            "对局编号": _state.episode_id, "脚本": _state.script_name or "无",
            "引擎": _state.engine_name or "无",
        },
        "文档": f"http://{_API_HOST}:{APP_PORT}/docs" if _API_HOST else "请设置 API_HOST 环境变量",
    }

@router.get("/health")
async def health():
    """健康检测：API 是否正常、到后端 gRPC 是否连通、仿真是否在运行。

    排障第一入口——启动/连接问题时先看这里。
    """
    grpc_ok = False; sim_running = False; grpc_detail = ""
    try:
        resp = _grpc_call("get_state")
        grpc_ok = resp.msg in ("FUNC_SUCCESS", "ENGINE_IS_NONE")
        sim_running = (resp.msg == "FUNC_SUCCESS")
        grpc_detail = resp.msg
    except Exception as e:
        grpc_detail = str(e)
    return {
        "api状态": "正常", "grpc连通": grpc_ok, "grpc详情": grpc_detail,
        "后端地址": f"{_HOST}:{_PORT}", "仿真运行中": sim_running,
        "当前引擎": _state.engine_name or "无", "对局编号": _state.episode_id,
        "已启动": _state.started, "已结束": _state.ended,
        "等待指令": _state.waiting_for_command,
        "历史动作数": len(_state.action_history), "日志文件": "sim_api.log",
    }

@router.get("/scripts")
async def list_scripts():
    """可用仿真脚本列表（与 /start、/reset 的 script_name 参数一致）。

    列表优先从后端 get_script_list 动态拉取（后端 sces.json 新增方案条目后
    无需重启 API 即可生效）；后端不可达时回退到本地配置。
    """
    fetched = _fetch_script_list()
    names = _known_scripts()
    return {
        "可用脚本": names, "默认脚本": DEFAULT_SCRIPT,
        "来源": "仿真后端" if fetched is not None else "本地配置（后端不可达）",
        "使用方式": "POST /start 或 /reset 时传入 script_name 参数，如 ?script_name=方案6-黑方艇数量_5",
    }

@router.get("/status")
async def get_status():
    """全局对局状态：已结束 / 对局结果 / 局内时间 / 资源快照 / 行动历史。

    决策循环的入口——Agent 每步先查它判断对局是否结束。
    """
    if not _state.engine_name:
        raise HTTPException(status_code=404, detail="仿真未启动")
    try:
        raw = _fetch_raw_state()
    except StateFetchError as e:
        _raise_on_state_error(e)
    intel = _build_enemy_intel(raw)
    current_time = _r2(raw.get("time", 0))
    episode_elapsed = max(0.0, current_time - _state.start_sim_time) if _state.start_sim_time else 0.0
    usv_summary = []
    for u in raw.get("white_usv_states", []):
        usv_summary.append({
            "name": u.get("name", "?"), "is_alive": u.get("is_alive", False),
            "position": u.get("position"), "speed": u.get("speed"),
            "course": u.get("course"), "is_locked": u.get("is_locked", False),
            "is_locking": u.get("is_locking", False), "is_frozen": u.get("is_frozen", False),
            "locked_attacker": u.get("locked_attacker", []), "locked_times": u.get("locked_times", 0),
        })
    uav_summary = []
    for u in raw.get("white_uav_states", []):
        uav_summary.append({
            "name": u.get("name", "?"), "is_alive": u.get("is_alive", False),
            "position": u.get("position"), "speed": u.get("speed"),
            "course": u.get("course"), "is_at_usv": u.get("is_at_usv", False),
            "battery_pct": _r2(u.get("battery_format", 0)),
        })
    resource_snapshot = {
        "统计": {
            "usv_total": len(usv_summary), "usv_alive": sum(1 for u in usv_summary if u["is_alive"]),
            "uav_total": len(uav_summary), "uav_alive": sum(1 for u in uav_summary if u["is_alive"]),
            "uav_flying": sum(1 for u in uav_summary if u["is_alive"] and not u.get("is_at_usv")),
            "enemy_visible": len(intel["active"]) + len(intel["passive"]),
        },
        "单位状态": {"white_usv_states": usv_summary, "white_uav_states": uav_summary},
        "观察信息": {"white_observation": {"雷达捕获": intel["active"], "被动告警": intel["passive"]}},
    }
    return {
        "对局编号": _state.episode_id, "已启动": _state.started, "已结束": _state.ended,
        "对局结果": _state.result, "脚本": _state.script_name,
        "真实时间": _state.start_real_time.strftime("%Y-%m-%d %H:%M:%S") if _state.start_real_time else None,
        "开局时间": _state.start_real_time.strftime("%Y-%m-%d %H:%M:%S.%f") if _state.start_real_time else None,
        "局内时间": _fmt_time(episode_elapsed), "等待指令": _state.waiting_for_command,
        "资源快照": resource_snapshot,
        "奖励信号": raw.get("env_score_flat", {}) or {}, "行动历史": _state.action_history,
    }
