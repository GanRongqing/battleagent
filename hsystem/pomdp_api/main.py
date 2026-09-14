"""
仿真 POMDP API

宏观步决策循环:
  1. GET  /status         → 检查 已结束 / 等待指令
  2. GET  /obs             → 语义观察（Plain Text）
  3. GET  /legal_actions   → 合法动作空间（JSON 字符串数组 + 参数说明）
  4. Agent 策略推演
  5. POST /apply           → 注入动作 → 环境推进 → 到达下一决策点
  6. 循环 1-5 直到 已结束=true

端点:
  GET  /status         全局状态同步（含行动历史镜像）
  GET  /obs            语义观察（状态、锁定、冻结、存活损毁）
  GET  /legal_actions  合法动作空间（JSON 字符串数组 + 参数说明）
  POST /apply          注入动作列表 → 推进一个宏观步
  POST /reset          重置 episode
  POST /start          启动仿真
  GET /stop           停止仿真
  GET  /result         对局结果分析（含完整行动历史）
  GET  /scripts        可用仿真脚本列表
  GET  /health         健康检测

监听端口: 8000 (环境变量 APP_PORT)
后端通信: BaseServer gRPC (6000)
"""

import os
import sys
import math
import json
import re
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, field, asdict

# main.py 放在子文件夹时，确保能 import 上级目录的 simulation
_PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PARENT_DIR not in sys.path:
    sys.path.insert(0, _PARENT_DIR)

import grpc
from fastapi import FastAPI, HTTPException
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, Field
from fastapi.responses import PlainTextResponse

from simulation import simserver_pb2
from simulation import simserver_pb2_grpc


# ╔══════════════════════════════════════════════════════════╗
# ║         配置（环境变量可覆盖）                            ║
# ╚══════════════════════════════════════════════════════════╝

# [迁移必改] 运行 base_server.py 的机器 IP
_HOST = os.getenv("SIM_HOST", "116.136.52.196")
# gRPC 端口，一般不用改
_PORT = os.getenv("SIM_PORT", "6000")
# gRPC 用户名
_USER_NAME = os.getenv("SIM_USER", "admin")
# [迁移必改] 本 API 对外可访问的地址（公网 IP 或域名），部署时必须设置
_API_HOST = os.getenv("API_HOST", "")
# 本 API 的监听端口
APP_PORT = int(os.getenv("APP_PORT", "8000"))
# 日志级别: DEBUG / INFO / WARNING / ERROR
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
# 设为 0 可禁用 /docs 和 /redoc
ENABLE_DOCS = os.getenv("ENABLE_DOCS", "1") == "1"

# 可用仿真脚本，名称需与后端 sces.json 中的 key 一致
AVAILABLE_SCRIPTS: List[str] = [
    "测试用例1",
    "scenario_10v10",
    "scenario_15v15",
    "scenario_20v20",
    "scenario_30v30",
    "scenario_10v10_rw",
    "scenario_composition",
]
# 默认脚本
DEFAULT_SCRIPT = "测试用例1"

# 宏观步步长（仿真秒数），即两次 Agent 决策之间推进的仿真时间
# 仿真速率约 100x，30 仿真秒 ≈ 0.3 真实秒，对 Agent 决策无感知延迟
MACRO_STEP_DURATION = float(os.getenv("MACRO_STEP", "30"))

# 无人机降落半径（米），UAV 与 USV 水平距离小于此值时允许直接降落
# 超过此距离时自动进入制导飞行，由系统计算航向引导 UAV 靠近 USV
LANDING_RADIUS = float(os.getenv("LANDING_RADIUS", "5"))


# ╔══════════════════════════════════════════════════════════╗
# ║                      日志配置                             ║
# ╚══════════════════════════════════════════════════════════╝

from logging.handlers import RotatingFileHandler

# 日志目录，与 main.py 同级的 api_logs 文件夹
_LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_logs")
# 运行日志与对局日志分开存放
_RUNTIME_LOG_DIR = os.path.join(_LOG_DIR, "runtime")
_GAME_LOG_DIR = os.path.join(_LOG_DIR, "games")
os.makedirs(_RUNTIME_LOG_DIR, exist_ok=True)
os.makedirs(_GAME_LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        RotatingFileHandler(
            os.path.join(_RUNTIME_LOG_DIR, "sim_api.log"), encoding="utf-8",
            maxBytes=10 * 1024 * 1024,  # 单文件最大 10MB
            backupCount=3,              # 保留最近 3 个备份
        ),
        logging.StreamHandler(),
    ],
)
_log = logging.getLogger("pomdp_api")


# ╔══════════════════════════════════════════════════════════╗
# ║                 持久化 gRPC 连接                          ║
# ╚══════════════════════════════════════════════════════════╝

_channel: Optional[grpc.Channel] = None
_stub: Optional[simserver_pb2_grpc.GreeterStub] = None


def _grpc_stub() -> simserver_pb2_grpc.GreeterStub:
    global _channel, _stub
    if _stub is None:
        _channel = grpc.insecure_channel(f"{_HOST}:{_PORT}")
        _stub = simserver_pb2_grpc.GreeterStub(channel=_channel)
        _log.info("gRPC 已连接 → %s:%s", _HOST, _PORT)
    return _stub


def _grpc_call(func_name: str, kwargs: dict = None,
               engine_name: str = None) -> simserver_pb2.MsgStr:
    """gRPC 请求封装"""
    msg = json.dumps({
        "source": "test",
        "ip": "test",
        "user_name": _USER_NAME,
        "engine_name": engine_name if engine_name is not None else _state.engine_name,
        "flag": "simulation",
        "func_name": func_name,
        "kwargs": kwargs or {},
    })
    _log.debug("gRPC → %s | kwargs=%s", func_name, kwargs)
    return _grpc_stub().control(simserver_pb2.MsgStr(msg=msg))


# ╔══════════════════════════════════════════════════════════╗
# ║                   FastAPI 应用                            ║
# ╚══════════════════════════════════════════════════════════╝

app = FastAPI(
    title="仿真 API",
    description="军事仿真推演系统 POMDP 语义交互接口",
    version="1.0",
    docs_url="/docs" if ENABLE_DOCS else None,
    redoc_url="/redoc" if ENABLE_DOCS else None,
)
app.add_middleware(GZipMiddleware, minimum_size=512)

# Strategy Library metadata CRUD (guarded: DB failure must not break the sim API)
try:
    import sys as _sys
    _ROOT_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if _ROOT_REPO not in _sys.path:
        _sys.path.insert(0, _ROOT_REPO)
    from strategy_library.router import router as _strategies_router
    from strategy_library.policy_router import router as _policy_router
    app.include_router(_strategies_router)
    app.include_router(_policy_router)
except Exception as _e:  # pragma: no cover
    logging.warning("strategy_library router not mounted: %s", _e)


# ╔══════════════════════════════════════════════════════════╗
# ║              请求模型                                     ║
# ╚══════════════════════════════════════════════════════════╝

class ActionItem(BaseModel):
    """单个动作：从 /legal_actions 中选择并填充参数后的动作字符串"""
    action_text: str = Field(
        ...,
        description="完整动作字符串，如 'white_usv1 移动 target_speed=15.0 target_course=90.0'",
    )
    action_type: str = Field(
        ...,
        description="动作类型: move | fly | lock | launch_uav | land_uav | noop",
    )


class ApplyRequest(BaseModel):
    """/apply 请求体：可包含多条动作，一次宏观步内对所有白方单位进行控制"""
    actions: List[ActionItem] = Field(
        ...,
        min_length=1,
        description="动作列表，可同时对多个单位下达指令",
    )


# ╔══════════════════════════════════════════════════════════╗
# ║                     全局对局状态                          ║
# ╚══════════════════════════════════════════════════════════╝

@dataclass
class EpisodeState:
    """对局级状态，封装所有跨请求的全局变量"""
    engine_name: str = ""
    episode_id: int = 0
    started: bool = False
    ended: bool = False
    result: Optional[str] = None
    waiting_for_command: bool = False
    release_until_time: Optional[float] = None  # 当前宏步目标推进到的引擎时间
    start_real_time: Optional[datetime] = None  # 对局开始的真实世界时间
    start_sim_time: float = 0.0                 # 对局开始时的引擎时间（用于计算局内时间）
    action_history: List[str] = field(default_factory=list)


_state = EpisodeState()


# ╔══════════════════════════════════════════════════════════╗
# ║                     对局日志                              ║
# ╚══════════════════════════════════════════════════════════╝


@dataclass
class StepRecord:
    """单步记录：一次 /apply 调用后的状态快照"""
    step: int
    sim_time: float                         # 仿真引擎时间（秒）
    episode_time: str                       # 局内时间 HH:MM:SS
    real_time: str                          # 真实世界时间
    actions: List[dict] = field(default_factory=list)       # 执行的动作及结果
    usv_states: List[dict] = field(default_factory=list)    # 白方 USV 摘要
    uav_states: List[dict] = field(default_factory=list)    # 白方 UAV 摘要
    active_enemies: List[dict] = field(default_factory=list)  # 雷达捕获的敌方
    passive_enemies: List[dict] = field(default_factory=list) # 被动告警的敌方
    reward: dict = field(default_factory=dict)              # 环境奖励信号
    events: List[str] = field(default_factory=list)         # 本步发生的关键事件


@dataclass
class GameLog:
    """一场对局的完整日志，用于 Agent 训练和行为分析"""
    episode_id: int
    script_name: str
    start_real_time: str = ""
    end_real_time: Optional[str] = None
    result: Optional[str] = None
    result_reason: Optional[str] = None
    steps: List[StepRecord] = field(default_factory=list)
    final_stats: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "episode_id": self.episode_id,
            "script_name": self.script_name,
            "start_real_time": self.start_real_time,
            "end_real_time": self.end_real_time,
            "result": self.result,
            "result_reason": self.result_reason,
            "total_steps": len(self.steps),
            "steps": [asdict(s) for s in self.steps],
            "final_stats": self.final_stats,
        }


_game_log: Optional[GameLog] = None


def _init_game_log(script_name: str):
    """开始新对局时初始化日志"""
    global _game_log
    _game_log = GameLog(
        episode_id=_state.episode_id,
        script_name=script_name,
        start_real_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


def _build_step_events(prev_step: Optional[StepRecord], raw: dict, intel: dict) -> List[str]:
    """比较前后两步，检测关键事件"""
    events: List[str] = []
    usvs = raw.get("white_usv_states", [])
    uavs = raw.get("white_uav_states", [])

    # 单位被击毁
    for u in usvs:
        if not u.get("is_alive"):
            name = u.get("name", "?")
            if prev_step:
                prev_usv = {s["name"]: s for s in prev_step.usv_states}
                if name in prev_usv and prev_usv[name].get("is_alive"):
                    events.append(f"{name} 被击毁")

    for u in uavs:
        if not u.get("is_alive"):
            name = u.get("name", "?")
            if prev_step:
                prev_uav = {s["name"]: s for s in prev_step.uav_states}
                if name in prev_uav and prev_uav[name].get("is_alive"):
                    events.append(f"{name} 被击毁")

    # 被冻结 / 解冻
    for u in usvs:
        name = u.get("name", "?")
        if u.get("is_alive"):
            is_frozen = u.get("is_frozen", False)
            if prev_step:
                prev_usv = {s["name"]: s for s in prev_step.usv_states}
                if name in prev_usv:
                    was_frozen = prev_usv[name].get("is_frozen", False)
                    if is_frozen and not was_frozen:
                        attackers = _locked_attacker_list(u.get("locked_attacker", []))
                        cause = attackers[0] if attackers else "未知"
                        events.append(f"{name} 被 {cause} 冻结")
                    elif not is_frozen and was_frozen:
                        events.append(f"{name} 解冻恢复")

    # 首次探测到新敌方
    new_names = [e["name"] for e in intel["active"]] + [e["name"] for e in intel["passive"]]
    if prev_step:
        prev_names = [e["name"] for e in prev_step.active_enemies] + [e["name"] for e in prev_step.passive_enemies]
        for n in new_names:
            if n not in prev_names:
                if any(e["name"] == n for e in intel["active"]):
                    events.append(f"雷达捕获新目标: {n}")
                else:
                    bearing = next((e.get("bearing") for e in intel["passive"] if e["name"] == n), None)
                    if bearing is not None:
                        events.append(f"被动告警: {n} 方位约{bearing}°")
                    else:
                        events.append(f"被动告警: {n}")

    # UAV 起飞/降落
    for u in uavs:
        name = u.get("name", "?")
        if u.get("is_alive"):
            is_at_usv = u.get("is_at_usv", False)
            if prev_step:
                prev_uav = {s["name"]: s for s in prev_step.uav_states}
                if name in prev_uav:
                    was_at_usv = prev_uav[name].get("is_at_usv", False)
                    if is_at_usv and not was_at_usv:
                        events.append(f"{name} 已降落")
                    elif not is_at_usv and was_at_usv:
                        events.append(f"{name} 已起飞")

    return events


def _record_step(raw: dict, action_results: List[dict]):
    global _game_log
    if _game_log is None:
        return

    engine_time = _r2(raw.get("time", 0))
    episode_elapsed = max(0.0, engine_time - _state.start_sim_time)
    intel = _build_enemy_intel(raw)

    usv_summary: List[dict] = []
    for u in raw.get("white_usv_states", []):
        usv_summary.append({
            "name": u.get("name", "?"),
            "is_alive": u.get("is_alive", False),
            "position": u.get("position"),
            "speed": u.get("speed"),
            "course": u.get("course"),
            "is_locked": u.get("is_locked", False),
            "is_locking": u.get("is_locking", False),
            "is_frozen": u.get("is_frozen", False),
            "locked_attacker": u.get("locked_attacker", []),
            "locked_times": u.get("locked_times", 0),
        })

    uav_summary: List[dict] = []
    for u in raw.get("white_uav_states", []):
        uav_summary.append({
            "name": u.get("name", "?"),
            "is_alive": u.get("is_alive", False),
            "position": u.get("position"),
            "speed": u.get("speed"),
            "course": u.get("course"),
            "is_at_usv": u.get("is_at_usv", False),
            "battery_pct": _r2(u.get("battery_format", 0)),
        })

    prev = _game_log.steps[-1] if _game_log.steps else None
    events = _build_step_events(prev, raw, intel)

    # 计算增量奖励（当前累计值 - 上一步累计值）
    cur_scores = raw.get("env_score_flat", {}) or {}
    prev_scores = prev.reward if prev else {}
    delta_reward = {}
    for k, v in cur_scores.items():
        prev_v = prev_scores.get(k, 0)
        if isinstance(v, (int, float)) and isinstance(prev_v, (int, float)):
            delta_reward[k] = v - prev_v
        else:
            delta_reward[k] = v

    record = StepRecord(
        step=len(_game_log.steps) + 1,
        sim_time=engine_time,
        episode_time=_fmt_time(episode_elapsed),
        real_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        actions=action_results,
        usv_states=usv_summary,
        uav_states=uav_summary,
        active_enemies=intel["active"],
        passive_enemies=intel["passive"],
        reward=delta_reward,
        events=events,
    )
    _game_log.steps.append(record)


def _finalize_game_log(raw: dict):
    """对局结束时封存日志"""
    global _game_log
    if _game_log is None:
        return

    _game_log.end_real_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    result_info = _build_result(raw)
    _game_log.result = result_info["对局结果"]
    _game_log.result_reason = result_info["结果说明"]

    usvs = raw.get("white_usv_states", [])
    uavs = raw.get("white_uav_states", [])
    intel = _build_enemy_intel(raw)
    _game_log.final_stats = {
        "usv_total": len(usvs),
        "usv_alive": sum(1 for u in usvs if u.get("is_alive")),
        "usv_dead": sum(1 for u in usvs if not u.get("is_alive")),
        "uav_total": len(uavs),
        "uav_alive": sum(1 for u in uavs if u.get("is_alive")),
        "uav_dead": sum(1 for u in uavs if not u.get("is_alive")),
        "enemy_radar": len(intel["active"]),
        "enemy_passive": len(intel["passive"]),
        "action_total": len(_state.action_history),
        "steps_total": len(_game_log.steps),
        "sim_duration": _r2(raw.get("time", 0)),
    }

    _save_game_log()


def _save_game_log():
    """将对局日志持久化到磁盘"""
    global _game_log
    if _game_log is None:
        return
    log_path = os.path.join(_GAME_LOG_DIR, f"game_{_game_log.episode_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    try:
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(_game_log.to_dict(), f, ensure_ascii=False, indent=2)
        _log.info("对局日志已保存: %s", log_path)
    except Exception as e:
        _log.error("对局日志保存失败: %s", e)


def _reset_episode_state(engine_name: str = ""):
    """重置对局状态到初始值，保留 engine_name 供后续使用"""
    _state.engine_name = engine_name
    _state.episode_id = 1
    _state.started = True
    _state.ended = False
    _state.result = None
    _state.waiting_for_command = True
    _state.release_until_time = None
    _state.start_real_time = datetime.now()
    _state.start_sim_time = 0.0
    _state.action_history.clear()


def _stop_episode_state():
    """标记对局已停止"""
    _state.started = False
    _state.ended = True
    _state.waiting_for_command = False
    if _state.result is None:
        _state.result = "Result.Tie"


# ╔══════════════════════════════════════════════════════════╗
# ║                   工具函数                                ║
# ╚══════════════════════════════════════════════════════════╝

def _fmt_time(sec: float) -> str:
    """仿真秒数 → HH:MM:SS"""
    if sec is None or (isinstance(sec, float) and math.isnan(sec)) or sec < 0:
        return "00:00:00"
    sec = float(sec)
    h, r = divmod(int(sec), 3600)
    m, s = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _r2(v) -> float:
    """浮点数保留 2 位小数"""
    if v is None:
        return 0.0
    if isinstance(v, float) and math.isnan(v):
        return 0.0
    return round(float(v), 2)


def _r6(v) -> float:
    """浮点数保留 6 位小数（坐标级精度）"""
    if v is None:
        return 0.0
    if isinstance(v, float) and math.isnan(v):
        return 0.0
    return round(float(v), 6)


def _position3d(raw_pos) -> List[float]:
    """将引擎返回的 position 转为 [x, y, z] 三维坐标，缺失维度补 0"""
    if not raw_pos or not isinstance(raw_pos, (list, tuple)):
        return [0.0, 0.0, 0.0]
    result = [_r6(v) for v in raw_pos[:3]]
    while len(result) < 3:
        result.append(0.0)
    return result


def _locked_attacker_list(val) -> List[str]:
    """将 locked_attacker 字段规范化为列表"""
    if not val:
        return []
    if isinstance(val, list):
        return [str(v) for v in val]
    return [str(val)]


def _parse_bool_result(resp) -> bool:
    """从 gRPC 响应中提取布尔结果"""
    if resp.data:
        try:
            return bool(json.loads(resp.data))
        except (json.JSONDecodeError, ValueError):
            return resp.msg == "FUNC_SUCCESS"
    return resp.msg == "FUNC_SUCCESS"


# ╔══════════════════════════════════════════════════════════╗
# ║         动作参数 schema（一处定义，多处引用）              ║
# ╚══════════════════════════════════════════════════════════╝

_ACTION_SCHEMAS: Dict[str, Dict[str, dict]] = {
    "move": {
        "target_speed": {
            "类型": "float", "范围": [0, 100], "单位": "米/秒",
            "说明": "期望速度",
        },
        "target_course": {
            "类型": "float", "范围": [0, 360], "单位": "度",
            "说明": "期望航向，正北为0°，顺时针方向为正",
        },
    },
    "fly": {
        "target_speed": {
            "类型": "float", "范围": [0, 100], "单位": "米/秒",
            "说明": "期望速度",
        },
        "target_course": {
            "类型": "float", "范围": [0, 360], "单位": "度",
            "说明": "期望航向，正北为0°，顺时针方向为正",
        },
    },
    "lock": {
        "target": {"类型": "str", "说明": "锁定目标名称"},
    },
    "launch_uav": {
        "home": {"类型": "str", "说明": "起飞母船名称"},
        "target_speed": {
            "类型": "float", "范围": [0, 100], "单位": "米/秒",
            "说明": "起飞后期望速度",
        },
        "target_course": {
            "类型": "float", "范围": [0, 360], "单位": "度",
            "说明": "起飞后期望航向，正北为0°，顺时针方向为正",
        },
    },
    "land_uav": {
        "target": {"类型": "str", "说明": "降落母船名称"},
    },
    "noop": {},
}


# ╔══════════════════════════════════════════════════════════╗
# ║              原始状态获取（每次必须最新，失败即报错）      ║
# ╚══════════════════════════════════════════════════════════╝

class StateFetchError(Exception):
    """获取状态失败异常"""
    def __init__(self, message: str, error_type: str = "STATE_FETCH_ERROR"):
        self.message = message
        self.error_type = error_type
        super().__init__(message)


def _fetch_raw_state() -> dict:
    """获取当前仿真原始状态，失败抛出 StateFetchError"""
    try:
        resp = _grpc_call("get_state")
    except Exception as e:
        _log.error("get_state gRPC 异常: %s", e)
        raise StateFetchError(
            f"无法连接仿真后端 ({_HOST}:{_PORT}): {e}",
            error_type="GRPC_ERROR",
        )

    if resp.msg == "ENGINE_IS_NONE":
        raise StateFetchError(
            "仿真引擎未启动，请先 POST /start 或 /reset",
            error_type="ENGINE_IS_NONE",
        )

    if resp.msg != "FUNC_SUCCESS":
        _log.error("get_state 返回非成功: %s", resp.msg)
        raise StateFetchError(
            f"获取仿真状态失败: {resp.msg}",
            error_type="STATE_ERROR",
        )

    if not resp.data:
        raise StateFetchError("仿真状态数据为空", error_type="STATE_EMPTY")

    try:
        return json.loads(resp.data)
    except json.JSONDecodeError as e:
        _log.error("get_state JSON 解析失败: %s", e)
        raise StateFetchError(
            f"仿真状态数据格式错误: {e}",
            error_type="STATE_PARSE_ERROR",
        )


def _raise_on_state_error(e: StateFetchError):
    """将 StateFetchError 映射为 HTTPException"""
    if e.error_type == "ENGINE_IS_NONE":
        raise HTTPException(status_code=404, detail=e.message)
    raise HTTPException(status_code=500, detail=e.message)


# ╔══════════════════════════════════════════════════════════╗
# ║           敌方情报综合                                    ║
# ╚══════════════════════════════════════════════════════════╝


def _build_enemy_intel(raw: dict) -> dict:
    """综合主动探测和被动告警，返回 {"active": [...], "passive": [...]}"""
    active: List[dict] = []
    passive: List[dict] = []
    seen_passive: set = set()

    for e in raw.get("white_observation", []):
        name = e.get("name", "")
        if name:
            active.append({
                "name": name,
                "position": e.get("position"),
                "velocity": e.get("velocity"),
            })

    for unit_list_name in ("white_usv_states", "white_uav_states"):
        for u in raw.get(unit_list_name, []):
            if not u.get("is_alive"):
                continue
            attackers = u.get("locked_attacker", [])
            if not attackers:
                continue
            if isinstance(attackers, str):
                attackers = [attackers]
            orientations = u.get("relative_orientation", [])
            if not isinstance(orientations, list):
                orientations = []
            unit_name = u.get("name", "?")

            for i, att_name in enumerate(attackers):
                att_name = str(att_name)
                if any(a["name"] == att_name for a in active):
                    continue
                bearing = None
                if i < len(orientations):
                    bearing = _r2(orientations[i])

                if att_name in seen_passive:
                    continue
                seen_passive.add(att_name)

                passive.append({
                    "name": att_name,
                    "bearing": bearing,
                    "detected_by": unit_name,
                    "source": "被动告警",
                })

    return {"active": active, "passive": passive}


# ╔══════════════════════════════════════════════════════════╗
# ║           观测构建（/obs — Plain Text）                    ║
# ╚══════════════════════════════════════════════════════════╝

def _build_obs_text(raw: dict) -> str:
    """将原始状态转为 LLM 友好的语义文本

    分段: [Info] / [我方无人艇] / [我方无人机] / [敌方情报] / [派生信号]
    敌方情报分两类: 雷达捕获（可锁定）/ 被动告警（仅方位）
    """
    lines: List[str] = []
    engine_time = _r2(raw.get("time", 0))
    episode_elapsed = max(0.0, engine_time - _state.start_sim_time)

    # ── [Info] ──
    lines.append("[Info]")
    if _state.start_real_time:
        lines.append(f"真实时间: {_state.start_real_time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"局内时间: {_fmt_time(episode_elapsed)}")
    lines.append("")

    intel = _build_enemy_intel(raw)
    active_enemies = intel["active"]
    passive_enemies = intel["passive"]

    # ── [我方无人艇] ──
    usvs = raw.get("white_usv_states", [])
    lines.append("[我方无人艇]")
    if not usvs:
        lines.append("  无")
    for u in usvs:
        name = u.get("name", "?")
        if not u.get("is_alive"):
            lines.append(f"  {name}: 已击毁")
            continue
        pos = _position3d(u.get("position"))
        spd = _r2(u.get("speed", 0))
        crs = _r2(u.get("course", 0))
        locked_times = u.get("locked_times", 0)
        is_locking = u.get("is_locking", False)
        is_frozen = u.get("is_frozen", False)
        locking_unit = u.get("locking_unit", "")
        uav_list = u.get("uav", [])

        attackers = _locked_attacker_list(u.get("locked_attacker"))
        orientations = u.get("relative_orientation", [])
        if not isinstance(orientations, list):
            orientations = []

        parts = [
            f"位置=({pos[0]}, {pos[1]}, {pos[2]})",
            f"速度={spd}米/秒",
            f"航向={crs}°",
        ]
        if is_locking and locking_unit:
            parts.append(f"正在锁定={locking_unit}")
        if is_frozen:
            parts.append("已冻结")
        if uav_list:
            parts.append(f"搭载无人机={uav_list}")
        else:
            parts.append("搭载无人机=无")

        if attackers:
            alert_parts = []
            for i, att in enumerate(attackers):
                if i < len(orientations):
                    alert_parts.append(f"{att}(方位约{_r2(orientations[i])}°)")
                else:
                    alert_parts.append(att)
            parts.append(f"被锁定: {', '.join(alert_parts)} ({locked_times}次)")

        lines.append(f"  {name}: 存活; {'; '.join(parts)}")
    lines.append("")

    # ── [我方无人机] ──
    uavs = raw.get("white_uav_states", [])
    lines.append("[我方无人机]")
    if not uavs:
        lines.append("  无")
    for u in uavs:
        name = u.get("name", "?")
        if not u.get("is_alive"):
            lines.append(f"  {name}: 已击毁")
            continue
        pos = _position3d(u.get("position"))
        spd = _r2(u.get("speed", 0))
        crs = _r2(u.get("course", 0))
        battery = _r2(u.get("battery", 0))
        battery_pct = _r2(u.get("battery_format", 0))
        is_charging = u.get("is_charging", False)
        is_at_usv = u.get("is_at_usv", False)
        home_name = u.get("home_name", "")

        parts = [
            f"位置=({pos[0]}, {pos[1]}, {pos[2]})",
            f"速度={spd}米/秒",
            f"航向={crs}°",
            f"剩余电量={battery}秒({battery_pct}%)",
        ]
        if is_charging:
            parts.append("充电中")
        if is_at_usv:
            parts.append(f"停靠在{home_name}")
        else:
            parts.append("飞行中")
        if home_name:
            parts.append(f"母船={home_name}")

        lines.append(f"  {name}: 存活; {'; '.join(parts)}")
    lines.append("")

    # ── [敌方情报] ──
    lines.append("[敌方情报]")
    if active_enemies:
        lines.append("  [雷达捕获] — 可执行锁定")
        for e in active_enemies:
            name = e.get("name", "?")
            p3 = _position3d(e.get("position"))
            lines.append(f"    {name}: 位置=({p3[0]}, {p3[1]}, {p3[2]})")
    else:
        lines.append("  [雷达捕获] 无")

    if passive_enemies:
        lines.append("  [被动告警] — 仅知方位，不可直接锁定")
        for e in passive_enemies:
            name = e.get("name", "?")
            bearing = e.get("bearing")
            detected_by = e.get("detected_by", "?")
            if bearing is not None:
                lines.append(f"    {name}: 方位约{bearing}°（被 {detected_by} 感知）")
            else:
                lines.append(f"    {name}: 方位未知（被 {detected_by} 感知）")
        lines.append("  建议: 朝告警方位起飞无人机，利用 UAV 60km 预警雷达捕获目标")
    else:
        lines.append("  [被动告警] 无")
    lines.append("")

    # ── [派生信号] ──
    lines.append("[派生信号]")
    freeze_lines: List[str] = []
    for u in usvs:
        if not u.get("is_alive"):
            continue
        if u.get("is_frozen"):
            name = u.get("name", "?")
            attackers = _locked_attacker_list(u.get("locked_attacker"))
            cause = attackers[0] if attackers else "未知来源"
            freeze_lines.append(f"  {name} 因 {cause} 被冻结")
    if freeze_lines:
        lines.append("冻结状态:")
        lines.extend(freeze_lines)
    else:
        lines.append("冻结状态: 无")

    alive_usv = sum(1 for u in usvs if u.get("is_alive"))
    alive_uav = sum(1 for u in uavs if u.get("is_alive"))
    flying_uav = sum(1 for u in uavs
                     if u.get("is_alive") and not u.get("is_at_usv"))
    total_enemy = len(active_enemies) + len(passive_enemies)
    lines.append(f"存活统计: 无人艇 {alive_usv}/{len(usvs)}, 无人机 {alive_uav}/{len(uavs)}, 空中 {flying_uav}")
    lines.append(f"敌方情报: 雷达捕获 {len(active_enemies)} + 被动告警 {len(passive_enemies)} = {total_enemy}")

    return "\n".join(lines)


# ╔══════════════════════════════════════════════════════════╗
# ║       合法动作构建（/legal_actions                          ║
# ╚══════════════════════════════════════════════════════════╝

def _build_legal_actions(raw: dict) -> dict:
    """生成合法动作空间，按类型分组为扁平字符串列表"""
    usvs = raw.get("white_usv_states", [])
    uavs = raw.get("white_uav_states", [])
    intel = _build_enemy_intel(raw)
    active_enemies = intel["active"]
    passive_enemies = intel["passive"]

    actions: Dict[str, List[str]] = {
        "[move]": [],
        "[lock]": [],
        "[launch_uav]": [],
        "[fly]": [],
        "[land_uav]": [],
    }
    notes: List[str] = []

    # [move] — 所有存活 USV
    for u in usvs:
        if u.get("is_alive"):
            actions["[move]"].append(
                f"{u['name']} 移动 target_speed=<值> target_course=<值>"
            )

    # [lock] — 所有存活 USV 对雷达捕获的敌方
    if active_enemies:
        for u in usvs:
            if not u.get("is_alive"):
                continue
            current = u.get("locking_unit", "")
            for e in active_enemies:
                en = e.get("name", "")
                if not en:
                    continue
                s = f"{u['name']} 锁定 {en}"
                if current == en:
                    s += "（当前已锁定，再次发送无效）"
                actions["[lock]"].append(s)

    # [launch_uav] — 甲板上的 UAV + 已停靠的 USV
    for u in uavs:
        if u.get("is_alive") and u.get("is_at_usv"):
            home = u.get("home_name", "")
            if home:
                actions["[launch_uav]"].append(
                    f"{u['name']} 从 {home} 起飞 target_speed=<值> target_course=<值>"
                )

    # [fly] + [land_uav] — 飞行中的 UAV
    for u in uavs:
        if u.get("is_alive") and not u.get("is_at_usv"):
            actions["[fly]"].append(
                f"{u['name']} 飞行 target_speed=<值> target_course=<值>"
            )
            for usv in usvs:
                if usv.get("is_alive"):
                    actions["[land_uav]"].append(
                        f"{u['name']} 降落到 {usv['name']}"
                    )

    if any(actions["[fly]"]) and any(actions["[land_uav]"]):
        notes.append("[fly] 和 [land_uav] 互斥，同一 UAV 每步只能选其一")
    if any(actions["[lock]"]):
        notes.append("标记「当前已锁定」的 [lock] 可发出但无效（会被跳过）")
    if not any(actions["[launch_uav]"]):
        notes.append("暂无 UAV 在甲板，[launch_uav] 为空")
    if not any(actions["[lock]"]):
        notes.append("暂无雷达捕获目标，[lock] 为空")

    # 移除空的动作类型
    actions = {k: v for k, v in actions.items() if v}

    result = {
        "参数": {
            "target_speed": "float, 0-100 m/s",
            "target_course": "float, 0-360°, 正北0°顺时针",
        },
        "noop": "空操作，等待一个宏观步 [noop]",
        "动作": actions,
    }
    if notes:
        result["备注"] = notes

    # 被动告警
    if passive_enemies:
        alerts: List[dict] = []
        for pe in passive_enemies:
            bearing = pe.get("bearing")
            detected_by = pe.get("detected_by", "?")
            alert = {"威胁": pe["name"]}
            if bearing is not None:
                alert["建议"] = f"{detected_by} 起飞 UAV 朝方位约{bearing}°搜索"
            else:
                alert["建议"] = f"{detected_by} 起飞 UAV 搜索"
            alerts.append(alert)
        result["被动告警"] = alerts

    return result


# ╔══════════════════════════════════════════════════════════╗
# ║           动作解析（从 action_text 提取单位和参数）        ║
# ╚══════════════════════════════════════════════════════════╝

def _extract_numeric_params(text: str, params: dict, action_type: str):
    """从动作字符串中提取 key=数值 参数，校验必填项"""
    for match in re.finditer(r'(target_speed|target_course)\s*=\s*([\d.]+)', text):
        key, val = match.group(1), match.group(2)
        try:
            params[key] = float(val)
        except ValueError:
            raise ValueError(f"参数 '{key}' 的值 '{val}' 不是有效数字")

    schema = _ACTION_SCHEMAS.get(action_type, {})
    for required_key in schema:
        if required_key not in params:
            raise ValueError(
                f"动作 '{action_type}' 缺少必填参数 '{required_key}'，"
                f"请在字符串中以 '{required_key}=<值>' 的形式提供"
            )


def _parse_action_text(action_text: str, action_type: str) -> dict:
    """从动作字符串中解析单位名和参数

    支持格式:
      noop:       "空操作，等待一个宏观步 [noop]"
      move:       "white_usv1 移动 target_speed=15.0 target_course=90.0 [move]"
      fly:        "white_uav1 飞行 target_speed=20.0 target_course=45.0 [fly]"
      lock:       "white_usv1 锁定 black_usv1 [lock]"
      launch_uav: "white_uav1 从 white_usv1 起飞 target_speed=20.0 target_course=45.0 [launch_uav]"
      land_uav:   "white_uav1 降落到 white_usv1 [land_uav]"
    """
    text = action_text.strip()

    if action_type == "noop":
        return {"unit": "", "action": "noop", "params": {}}

    # 去掉末尾标记和注释
    text = re.sub(r'\s*\[.*?\]\s*$', '', text).strip()
    text = re.sub(r'\s*（[^）]*）\s*$', '', text).strip()

    params: Dict[str, Any] = {}

    if action_type == "lock":
        parts = text.split()
        if len(parts) < 3 or parts[1] != "锁定":
            raise ValueError(
                f"无法解析 lock 动作，期望格式 '单位名 锁定 目标名': '{action_text}'"
            )
        return {"unit": parts[0], "action": "lock", "params": {"target": parts[2]}}

    if action_type == "land_uav":
        parts = text.split()
        if len(parts) < 3 or parts[1] != "降落到":
            raise ValueError(
                f"无法解析 land_uav 动作，期望格式 '无人机名 降落到 母船名': '{action_text}'"
            )
        return {"unit": parts[0], "action": "land_uav", "params": {"target": parts[2]}}

    if action_type == "launch_uav":
        home_match = re.search(r'从\s+(\S+)', text)
        if not home_match:
            raise ValueError(f"无法提取母船名: '{action_text}'")
        unit = text.split()[0]
        params["home"] = home_match.group(1)
        _extract_numeric_params(text, params, action_type)
        return {"unit": unit, "action": "launch_uav", "params": params}

    if action_type in ("move", "fly"):
        parts = text.split()
        if len(parts) < 2:
            raise ValueError(f"无法解析 {action_type} 动作: '{action_text}'")
        _extract_numeric_params(text, params, action_type)
        return {"unit": parts[0], "action": action_type, "params": params}

    raise ValueError(f"未知动作类型: '{action_type}'")


# ╔══════════════════════════════════════════════════════════╗
# ║              动作执行（映射到 gRPC 引擎指令）              ║
# ╚══════════════════════════════════════════════════════════╝

def _execute_one_action(parsed: dict) -> dict:
    """执行单个动作

    Returns:
        {"ok": bool, "skipped": bool, "detail": str}  -- skipped=true 表示跳过执行（如重复锁定）
    """
    a = parsed["action"]
    p = parsed["params"]
    unit = parsed["unit"]

    try:
        if a == "noop":
            _log.info("空操作")
            return {"ok": True, "skipped": False, "detail": "空操作"}

        elif a in ("move", "fly"):
            spd = p.get("target_speed", 10.0)
            crs = p.get("target_course", 0.0)
            resp = _grpc_call("send_command", kwargs={"cmd": {
                "unit_name": unit,
                "target_speed": spd,
                "target_course": crs,
            }})
            ok = (resp.msg == "FUNC_SUCCESS")
            label = "移动" if a == "move" else "飞行"
            detail = f"{unit} {label} speed={spd} course={crs}"
            if ok:
                _log.info(detail)
            else:
                detail += f" 失败: {resp.msg}"
            return {"ok": ok, "skipped": False, "detail": detail}

        elif a == "lock":
            target = p.get("target", "")
            # 检查是否已锁定同一目标（重复锁定视为无效指令）
            try:
                raw = _fetch_raw_state()
                for u in raw.get("white_usv_states", []):
                    if u.get("name") == unit and u.get("is_alive"):
                        if u.get("locking_unit", "") == target:
                            detail = f"{unit} 已锁定 {target}，指令无效"
                            _log.info(detail)
                            return {"ok": True, "skipped": True, "detail": detail}
                        break
            except StateFetchError:
                pass  # 无法确认时继续执行

            resp = _grpc_call("cmd_lock", kwargs={
                "unit1_name": unit,
                "unit2_name": target,
            })
            ok = _parse_bool_result(resp)
            detail = f"{unit} 锁定 {target}"
            if ok:
                _log.info(detail)
            else:
                detail += f" 失败: {resp.msg}"
            return {"ok": ok, "skipped": False, "detail": detail}

        elif a == "launch_uav":
            home = p.get("home", "")
            spd = p.get("target_speed", 10.0)
            crs = p.get("target_course", 0.0)
            resp = _grpc_call("cmd_uav_takeoff", kwargs={
                "unit_name": unit,
                "home_name": home,
                "target_speed": spd,
                "target_course": crs,
            })
            ok = _parse_bool_result(resp)
            detail = f"{unit} 从 {home} 起飞 speed={spd} course={crs}"
            if ok:
                _log.info(detail)
            else:
                detail += f" 失败: {resp.msg}"
            return {"ok": ok, "skipped": False, "detail": detail}

        elif a == "land_uav":
            target = p.get("target", "")
            # 获取 UAV 与目标 USV 的水平距离
            try:
                raw = _fetch_raw_state()
                uav_pos, usv_pos = None, None
                for u in raw.get("white_uav_states", []):
                    if u.get("name") == unit and u.get("is_alive"):
                        uav_pos = u.get("position", [0, 0])[:2]
                        break
                for u in raw.get("white_usv_states", []):
                    if u.get("name") == target and u.get("is_alive"):
                        usv_pos = u.get("position", [0, 0])[:2]
                        break
                if uav_pos and usv_pos:
                    dx, dy = uav_pos[0] - usv_pos[0], uav_pos[1] - usv_pos[1]
                    dist = math.sqrt(dx * dx + dy * dy)
                else:
                    dist = float("inf")
            except StateFetchError:
                dist = float("inf")

            # 制导飞行: 距离超标时自动计算方位角，引导 UAV 靠近 USV
            if dist > LANDING_RADIUS and uav_pos and usv_pos:
                dx = usv_pos[0] - uav_pos[0]
                dy = usv_pos[1] - uav_pos[1]
                bearing = math.degrees(math.atan2(dx, dy))
                if bearing < 0:
                    bearing += 360.0
                guide_speed = 50.0
                resp = _grpc_call("send_command", kwargs={"cmd": {
                    "unit_name": unit,
                    "target_speed": guide_speed,
                    "target_course": _r2(bearing),
                }})
                ok = (resp.msg == "FUNC_SUCCESS")
                detail = (
                    f"{unit} 距 {target} {dist:.0f}米, "
                    f"进入制导飞行: speed={guide_speed} course={_r2(bearing)}°"
                )
                if not ok:
                    detail += f" 失败: {resp.msg}"
                _log.info(detail)
                return {"ok": ok, "skipped": False, "detail": detail}

            # 降落: 距离在阈值内，执行挂载
            resp = _grpc_call("cmd_uav_land", kwargs={
                "uav_name": unit,
                "usv_name": target,
            })
            ok = _parse_bool_result(resp)
            detail = f"{unit} 降落到 {target} (距离 {dist:.0f}米)"
            if ok:
                _log.info(detail)
            else:
                detail += f" 失败: {resp.msg}"
            return {"ok": ok, "skipped": False, "detail": detail}

        else:
            return {"ok": False, "skipped": False, "detail": f"未知动作类型: {a}"}

    except Exception as e:
        _log.error("动作执行异常 | %s %s %s | %s", a, unit, p, str(e))
        return {"ok": False, "skipped": False, "detail": f"异常: {str(e)}"}


# ╔══════════════════════════════════════════════════════════╗
# ║              对局结果分析（/result）                       ║
# ╚══════════════════════════════════════════════════════════╝

def _build_result(raw: dict) -> dict:
    """分析对局结果：输赢判断 + 存活统计"""
    usvs = raw.get("white_usv_states", [])
    uavs = raw.get("white_uav_states", [])
    intel = _build_enemy_intel(raw)
    all_enemy_names = [e["name"] for e in intel["active"]] + [e["name"] for e in intel["passive"]]
    alive_usvs = [u["name"] for u in usvs if u.get("is_alive")]
    dead_usvs = [u["name"] for u in usvs if not u.get("is_alive")]
    alive_uavs = [u["name"] for u in uavs if u.get("is_alive")]
    dead_uavs = [u["name"] for u in uavs if not u.get("is_alive")]

    result = "未结束"
    reason = "仿真仍在运行中"

    if raw.get("ended", False):
        engine_reason = raw.get("ended_reason", "")
        if engine_reason:
            reason = engine_reason

        if "敌方所有" in engine_reason or "敌方" in engine_reason and "击毁" in engine_reason:
            result = "Result.Victory"
        elif "我方所有" in engine_reason or "突破" in engine_reason:
            result = "Result.Defeat"
        elif not alive_usvs and not alive_uavs:
            result = "Result.Defeat"
            reason = reason or "我方所有单位被击毁"
        elif not alive_usvs:
            result = "Result.Defeat"
            reason = reason or "我方所有无人艇被击毁"
        else:
            # 综合判断：根据奖励信号
            scores = raw.get("env_score_flat", {})
            if scores:
                total = sum(v for v in scores.values()
                           if isinstance(v, (int, float)))
                if total > 0:
                    result = "Result.Victory"
                    reason = reason or f"综合得分为正: {total}"
                elif total < 0:
                    result = "Result.Defeat"
                    reason = reason or f"综合得分为负: {total}"
                else:
                    result = "Result.Tie"
                    reason = reason or "综合得分为零"
            else:
                result = "Result.Tie"
                reason = reason or "对局结束，无法判定明确胜负"

    return {
        "对局结果": result,
        "结果说明": reason,
        "存活统计": {
            "无人艇": {"存活": alive_usvs, "已击毁": dead_usvs},
            "无人机": {"存活": alive_uavs, "已击毁": dead_uavs},
        },
        "敌方统计": {
            "雷达捕获": [e["name"] for e in intel["active"]],
            "被动告警": [e["name"] for e in intel["passive"]],
            "总数": len(all_enemy_names),
        },
        "奖励信号": raw.get("env_score_flat", {}) or {},
        "行动总数": len(_state.action_history),
    }


# ╔══════════════════════════════════════════════════════════╗
# ║              共享初始化逻辑                               ║
# ╚══════════════════════════════════════════════════════════╝

def _do_init(script_name: str) -> str:
    """初始化仿真引擎，返回 engine_name；先尝试终止残留引擎"""
    # 先清理残留引擎
    try:
        _grpc_call("terminate", kwargs={}, engine_name="")
    except Exception:
        pass

    try:
        resp = _grpc_call("init",
                          kwargs={"fname": script_name, "update": True},
                          engine_name="")
    except Exception as e:
        _log.error("init gRPC 异常: %s", e)
        raise HTTPException(status_code=500, detail=f"连接后端失败: {e}")

    # 若后端有残留引擎，再次强制终止后重试
    if resp.msg == "ENGINE_SIM_RUNNING":
        _log.warning("ENGINE_SIM_RUNNING，强制终止后重试")
        try:
            _grpc_call("terminate", kwargs={}, engine_name="")
        except Exception:
            pass
        try:
            resp = _grpc_call("init",
                              kwargs={"fname": script_name, "update": True},
                              engine_name="")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"连接后端失败: {e}")

    if resp.msg != "FUNC_SUCCESS":
        raise HTTPException(status_code=500, detail=f"仿真启动失败: {resp.msg}")

    init_data = json.loads(resp.data) if resp.data else {}
    return init_data.get("engine_name", "")


def _calibrate_epoch():
    """校准对局开始的引擎时间，失败时设为 0"""
    try:
        raw = _fetch_raw_state()
        _state.start_sim_time = _r2(raw.get("time", 0))
    except StateFetchError as e:
        _state.start_sim_time = 0.0
        _log.warning("校准 epoch 失败: %s", e.message)


# ╔══════════════════════════════════════════════════════════╗
# ║              API 端点                                     ║
# ╚══════════════════════════════════════════════════════════╝

# ─── GET / ──────────────────────────────────────────

@app.get("/")
async def index():
    """API 首页，显示服务信息与端点清单"""
    return {
        "服务": "仿真 POMDP API",
        "版本": "1.0",
        "说明": "军事仿真推演系统 POMDP 语义交互接口，遵循部分可观测马尔可夫决策过程（Partially Observable Markov Decision Process, POMDP）",
        "决策循环": [
            "GET  /status        → 检查 已结束 / 等待指令",
            "GET  /obs            → 获取语义观察（Plain Text）",
            "GET  /legal_actions  → 获取合法动作空间",
            "POST /apply          → 注入动作，推进一个宏观步",
            "重复直到 已结束=true",
        ],
        "端点": {
            "GET  /":               "本页面",
            "GET  /health":         "健康检测",
            "GET  /scripts":        "可用仿真脚本列表",
            "POST /start":          "启动仿真（episode_id 递增）",
            "GET /stop":           "停止仿真（保留行动历史）",
            "POST /reset":          "重置仿真（终止 → 清理 → 重新初始化）",
            "GET  /status":         "全局状态同步（含资源快照与行动历史镜像）",
            "GET  /obs":            "语义观察（Plain Text，状态/锁定/冻结/存活损毁）",
            "GET  /legal_actions":  "合法动作空间（JSON 字符串数组 + 参数说明）",
            "POST /apply":          "注入动作列表 → 推进一个宏观步",
            "GET  /result":         "对局结果分析（含完整行动历史）",
            "GET  /game_log":       "对局日志（含每步状态/事件/奖励）",
        },
        "配置": {
            "仿真后端": f"{_HOST}:{_PORT}",
            "宏观步步长": f"{MACRO_STEP_DURATION}s（仿真秒数）",
            "降落半径": f"{LANDING_RADIUS}m",
        },
        "当前状态": {
            "已启动": _state.started,
            "已结束": _state.ended,
            "对局编号": _state.episode_id,
            "引擎": _state.engine_name or "无",
        },
        "文档": f"http://{_API_HOST}:{APP_PORT}/docs" if _API_HOST else "请设置 API_HOST 环境变量",
    }


# ─── GET /health ─────────────────────────────────────

@app.get("/health")
async def health():
    """健康检测"""
    grpc_ok = False
    sim_running = False
    grpc_detail = ""
    try:
        resp = _grpc_call("get_state")
        grpc_ok = resp.msg in ("FUNC_SUCCESS", "ENGINE_IS_NONE")
        sim_running = (resp.msg == "FUNC_SUCCESS")
        grpc_detail = resp.msg
    except Exception as e:
        grpc_detail = str(e)

    return {
        "api状态": "正常",
        "grpc连通": grpc_ok,
        "grpc详情": grpc_detail,
        "后端地址": f"{_HOST}:{_PORT}",
        "仿真运行中": sim_running,
        "当前引擎": _state.engine_name or "无",
        "对局编号": _state.episode_id,
        "已启动": _state.started,
        "已结束": _state.ended,
        "等待指令": _state.waiting_for_command,
        "历史动作数": len(_state.action_history),
        "日志文件": "sim_api.log",
    }


# ─── GET /scripts ────────────────────────────────────

@app.get("/scripts")
async def list_scripts():
    """列出可用仿真脚本"""
    return {
        "可用脚本": AVAILABLE_SCRIPTS,
        "默认脚本": DEFAULT_SCRIPT,
        "使用方式": "POST /start 或 /reset 时传入 script_name 参数",
    }


# ─── POST /start ─────────────────────────────────────

@app.post("/start")
async def start(script_name: str = DEFAULT_SCRIPT):
    """启动新仿真，episode_id 递增，清空历史"""
    global _state

    _log.info("POST /start | script=%s", script_name)

    if script_name not in AVAILABLE_SCRIPTS:
        raise HTTPException(
            status_code=400,
            detail=f"未知脚本 '{script_name}'，可用: {AVAILABLE_SCRIPTS}",
        )

    # 如果本进程已知有活跃引擎，检查状态
    if _state.engine_name:
        try:
            check = _grpc_call("get_state")
            if check.msg == "FUNC_SUCCESS":
                raise HTTPException(
                    status_code=409,
                    detail="仿真已在运行中，请先 GET /stop 或使用 POST /reset",
                )
        except HTTPException:
            raise
        except Exception as e:
            _log.warning("start 前检查状态异常: %s", e)
            _state.engine_name = ""

    engine_name = _do_init(script_name)
    _state.engine_name = engine_name
    _state.episode_id += 1
    _state.started = True
    _state.ended = False
    _state.result = None
    _state.waiting_for_command = True
    _state.release_until_time = None
    _state.start_real_time = datetime.now()
    _state.action_history.clear()
    _init_game_log(script_name)
    _calibrate_epoch()

    _log.info("启动成功 | episode=%d | engine=%s | epoch=%.1f",
              _state.episode_id, _state.engine_name, _state.start_sim_time)

    return {
        "成功": True,
        "说明": f"仿真已启动，第 {_state.episode_id} 局",
        "对局编号": _state.episode_id,
        "已启动": True,
        "已结束": False,
        "等待指令": True,
        "真实时间": _state.start_real_time.strftime("%Y-%m-%d %H:%M:%S"),
        "局内时间": "00:00:00",
    }


# ─── GET /stop ──────────────────────────────────────

@app.get("/stop")
async def stop():
    """停止当前仿真，保留行动历史"""
    global _state

    _log.info("GET /stop | engine=%s", _state.engine_name)

    if not _state.engine_name:
        raise HTTPException(status_code=404, detail="仿真未在运行")

    # 先获取最终状态并封存对局日志，再终止引擎
    try:
        raw = _fetch_raw_state()
        _finalize_game_log(raw)
    except Exception as e:
        _log.warning("stop 前获取状态/封存日志失败: %s", e)

    try:
        resp = _grpc_call("terminate", kwargs={})
    except Exception as e:
        _log.error("terminate gRPC 异常: %s", e)
        raise HTTPException(status_code=500, detail=f"连接后端失败: {e}")

    if resp.msg not in ("FUNC_SUCCESS", "ENGINE_IS_NONE"):
        raise HTTPException(status_code=500, detail=f"停止失败: {resp.msg}")

    _stop_episode_state()
    _state.engine_name = ""

    _log.info("已停止 | episode=%d | 历史动作=%d",
              _state.episode_id, len(_state.action_history))

    return {
        "成功": True,
        "说明": "仿真已停止",
        "对局编号": _state.episode_id,
        "已启动": False,
        "已结束": True,
        "对局结果": _state.result,
        "历史动作数": len(_state.action_history),
    }


# ─── POST /reset ─────────────────────────────────────

@app.post("/reset")
async def reset(script_name: str = DEFAULT_SCRIPT):
    """重置仿真：终止 → 清理 → 重新初始化，episode_id 重置为 1"""
    global _state

    _log.info("POST /reset | script=%s", script_name)

    if script_name not in AVAILABLE_SCRIPTS:
        raise HTTPException(
            status_code=400,
            detail=f"未知脚本 '{script_name}'，可用: {AVAILABLE_SCRIPTS}",
        )

    # 封存上一局日志再重置
    if _state.engine_name:
        try:
            raw = _fetch_raw_state()
            _finalize_game_log(raw)
        except Exception as e:
            _log.warning("reset 前封存日志失败: %s", e)

    # 多次尝试终止，确保后端残留引擎被清理
    for _ in range(2):
        try:
            _grpc_call("terminate", kwargs={}, engine_name="")
        except Exception:
            pass

    engine_name = _do_init(script_name)
    _reset_episode_state(engine_name)
    _init_game_log(script_name)
    _calibrate_epoch()

    _log.info("重置成功 | episode=1 | engine=%s | epoch=%.1f",
              _state.engine_name, _state.start_sim_time)

    return {
        "成功": True,
        "说明": "Reset",
        "已重置": True,
        "对局编号": 1,
    }


# ─── GET /status ─────────────────────────────────────

@app.get("/status")
async def get_status():
    """全局状态与时间轴同步

    返回底层真实快照，用于同步、评估和日志。
    包含行动历史作为 /legal_actions 的冗余镜像。
    """
    global _state

    if not _state.engine_name:
        raise HTTPException(
            status_code=404,
            detail="仿真未启动，请先 POST /start 或 /reset",
        )

    try:
        raw = _fetch_raw_state()
    except StateFetchError as e:
        _raise_on_state_error(e)

    engine_time = _r2(raw.get("time", 0))
    episode_elapsed = max(0.0, engine_time - _state.start_sim_time)

    # waiting_for_command 机制
    if _state.release_until_time is not None:
        if engine_time >= _state.release_until_time:
            _state.waiting_for_command = True
            _state.release_until_time = None
        else:
            _state.waiting_for_command = False

    # 终止信号
    if raw.get("ended", False) and not _state.ended:
        _state.ended = True
        _state.waiting_for_command = False
        result_info = _build_result(raw)
        _state.result = result_info["对局结果"]
        _finalize_game_log(raw)

    # 资源快照：统计 + 单位状态 + 观察信息
    usvs_raw = raw.get("white_usv_states", [])
    uavs_raw = raw.get("white_uav_states", [])
    intel = _build_enemy_intel(raw)

    # 构建单位状态（保留引擎原始字段，增加被锁方位）
    usv_states: List[dict] = []
    for u in usvs_raw:
        entry: dict = {}
        for k in ("name", "is_alive", "position", "velocity", "course", "speed",
                   "is_locked", "is_locking", "is_frozen",
                   "locked_attacker", "relative_orientation",
                   "locking_unit", "locked_times", "uav"):
            if k in u:
                entry[k] = u[k]
        usv_states.append(entry)

    uav_states: List[dict] = []
    for u in uavs_raw:
        entry: dict = {}
        for k in ("name", "is_alive", "position", "velocity", "course", "speed",
                   "battery", "battery_format", "is_charging", "is_at_usv", "home_name"):
            if k in u:
                entry[k] = u[k]
        uav_states.append(entry)

    resource_snapshot = {
        "统计": {
            "usv_total": len(usvs_raw),
            "usv_alive": sum(1 for u in usvs_raw if u.get("is_alive")),
            "uav_total": len(uavs_raw),
            "uav_alive": sum(1 for u in uavs_raw if u.get("is_alive")),
            "uav_flying": sum(1 for u in uavs_raw
                             if u.get("is_alive") and not u.get("is_at_usv")),
            "enemy_visible": len(intel["active"]) + len(intel["passive"]),
        },
        "单位状态": {
            "white_usv_states": usv_states,
            "white_uav_states": uav_states,
        },
        "观察信息": {
            "white_observation": {
                "雷达捕获": intel["active"],
                "被动告警": intel["passive"],
            },
        },
    }

    return {
        "对局编号": _state.episode_id,
        "已启动": _state.started,
        "已结束": _state.ended,
        "对局结果": _state.result,
        "真实时间": _state.start_real_time.strftime("%Y-%m-%d %H:%M:%S") if _state.start_real_time else None,
        "局内时间": _fmt_time(episode_elapsed),
        "等待指令": _state.waiting_for_command,
        "资源快照": resource_snapshot,
        "奖励信号": raw.get("env_score_flat", {}) or {},
        "行动历史": _state.action_history,
    }


# ─── GET /obs ────────────────────────────────────────

@app.get("/obs", response_class=PlainTextResponse)
async def get_obs():
    """语义观察，返回 Plain Text

    分段: [Info] / [我方无人艇] / [我方无人机] / [敌方情报] / [派生信号]
    """
    if not _state.engine_name:
        raise HTTPException(status_code=404, detail="仿真未启动")

    try:
        raw = _fetch_raw_state()
    except StateFetchError as e:
        _raise_on_state_error(e)

    return _build_obs_text(raw)


# ─── GET /legal_actions ──────────────────────────────

@app.get("/legal_actions")
async def get_legal_actions():
    """合法动作空间（动作掩码）

    返回当前物理状态下所有可执行的动作集合。
    每个动作为一个完整字符串，Agent 直接选用并填充参数后 POST /apply。
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


# ─── POST /apply ─────────────────────────────────────

@app.post("/apply")
async def apply_actions(req: ApplyRequest):
    """状态转移触发器

    接收 Agent 选择的动作列表，注入引擎，推进一个宏观步。
    fire-and-forget 设计：返回即表示已接收。
    """
    global _state

    _log.info("POST /apply | %d 个动作", len(req.actions))

    if not _state.engine_name:
        raise HTTPException(status_code=404, detail="仿真未启动")

    if _state.ended:
        raise HTTPException(
            status_code=409,
            detail="当前 episode 已结束，请 POST /reset 开启新局",
        )

    # 逐条校验 + 执行
    results: List[dict] = []
    skipped_msgs: List[str] = []

    for i, item in enumerate(req.actions):
        # 验证 action_type
        if item.action_type not in _ACTION_SCHEMAS:
            raise HTTPException(
                status_code=400,
                detail=f"[动作{i+1}] 未知动作类型 '{item.action_type}'，"
                       f"合法值: {list(_ACTION_SCHEMAS.keys())}",
            )

        # 解析
        try:
            parsed = _parse_action_text(item.action_text, item.action_type)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"[动作{i+1}] {e}")

        # 校验必填参数
        schema = _ACTION_SCHEMAS.get(item.action_type, {})
        for key in schema:
            if key not in parsed["params"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"[动作{i+1}] 动作 '{item.action_type}' 缺少必填参数 '{key}'",
                )

        # 执行
        exec_result = _execute_one_action(parsed)
        results.append({
            "序号": i + 1,
            "动作": item.action_text.strip(),
            "成功": exec_result["ok"],
            "跳过": exec_result.get("skipped", False),
            "详情": exec_result["detail"],
        })

        if exec_result.get("skipped"):
            skipped_msgs.append(f"[动作{i+1}] {exec_result['detail']}")

        if not exec_result["ok"]:
            raise HTTPException(
                status_code=400,
                detail=f"[动作{i+1}] {exec_result['detail']}",
            )

    # 记录到历史
    for item in req.actions:
        _state.action_history.append(item.action_text.strip())

    # 推进宏观步
    try:
        raw = _fetch_raw_state()
        current_time = _r2(raw.get("time", 0))
        _state.release_until_time = current_time + MACRO_STEP_DURATION
        # 记录对局日志（动作执行后的状态快照）
        _record_step(raw, results)

        # 检查对局是否已自然结束
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
        "成功": True,
        "已队列": True,
        "执行结果": results,
        "执行统计": f"{len(results)} 个动作: {success_count} 成功, {skip_count} 跳过",
    }
    if skipped_msgs:
        response["跳过详情"] = skipped_msgs

    _log.info("apply 完成 | %s | release_until=%.1f",
              response["执行统计"], _state.release_until_time)

    return response


# ─── GET /result ─────────────────────────────────────

@app.get("/result")
async def get_result():
    """对局结果分析，含完整行动历史"""
    if not _state.engine_name and not _state.ended:
        raise HTTPException(status_code=404, detail="仿真未启动")

    try:
        raw = _fetch_raw_state()
    except StateFetchError as e:
        if e.error_type == "ENGINE_IS_NONE" and _state.ended:
            return {
                "对局结果": _state.result or "Result.Tie",
                "结果说明": "仿真引擎已停止",
                "行动总数": len(_state.action_history),
                "行动历史": _state.action_history,
            }
        elif e.error_type == "GRPC_ERROR":
            raise HTTPException(status_code=500, detail=e.message)
        else:
            raise HTTPException(status_code=500, detail=e.message)

    result = _build_result(raw)
    result["行动历史"] = _state.action_history
    return result


# ─── GET /game_log ───────────────────────────────────

@app.get("/game_log")
async def get_game_log():
    """返回当前对局的完整日志

    每步记录包含: 动作、动作结果、USV/UAV 状态、敌方情报、奖励信号、关键事件。
    对局结束时自动保存到 api_logs/games/ 目录。
    """
    global _game_log
    if _game_log is None:
        raise HTTPException(status_code=404, detail="暂无对局日志，请先 POST /start 或 /reset")

    return {
        "当前对局": _game_log.to_dict(),
        "说明": "每步记录含: 动作与结果 | USV状态 | UAV状态 | 雷达捕获 | 被动告警 | 奖励 | 事件",
        "日志文件": f"api_logs/games/game_{_game_log.episode_id}_*.json",
    }


# ╔══════════════════════════════════════════════════════════╗
# ║                   启动入口                                ║
# ╚══════════════════════════════════════════════════════════╝

if __name__ == "__main__":
    import uvicorn
    print("=" * 56)
    print("  仿真 POMDP API")
    print(f"  监听: 0.0.0.0:{APP_PORT}")
    print(f"  后端: {_HOST}:{_PORT}")
    print(f"  用户: {_USER_NAME}")
    print(f"  日志: sim_api.log")
    if _API_HOST:
        print(f"  文档: http://{_API_HOST}:{APP_PORT}/docs")
    else:
        print("  ⚠ 未设置 API_HOST，/docs 链接不可用，请设置后重启")
    print(f"  宏观步步长: {MACRO_STEP_DURATION}s（仿真秒数）")
    print("=" * 56)
    uvicorn.run(app, host="0.0.0.0", port=APP_PORT, log_level="info")
