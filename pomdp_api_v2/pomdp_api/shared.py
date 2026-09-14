"""仿真 POMDP API — 公共层：配置、模型、gRPC、状态、业务函数"""

import os
import sys
import math
import json
import re
import time
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, field, asdict

# pomdp_api 位于仓库根目录下（根 config.py 也在此），仿真包在兄弟目录 hsystem/ 中
_HSYSTEM_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "hsystem")
_ROOT_DIR = os.path.dirname(_HSYSTEM_DIR)
for _d in (_ROOT_DIR, _HSYSTEM_DIR):
    if _d not in sys.path:
        sys.path.insert(0, _d)

import grpc
from fastapi import HTTPException
from pydantic import BaseModel, Field

from simulation import simserver_pb2
from simulation import simserver_pb2_grpc
from simulation.simserver_pb2 import MsgStr


# 日志（从独立模块导入）
from pomdp_api.logger import _log, _GAME_LOG_DIR

# ╔══════════════════════════════════════════════════════════╗
# ║         配置（连接配置在仓库根 config.py，环境变量可覆盖）║
# ╚══════════════════════════════════════════════════════════╝

# 连接配置集中在仓库根 config.py（本文件只引用，沿用既有变量名）
from config import (
    SIM_HOST as _HOST,        # 运行 base_server.py 的机器 IP
    SIM_PORT as _PORT,        # gRPC 端口，一般不用改
    SIM_USER as _USER_NAME,   # gRPC 用户名
    API_HOST as _API_HOST,    # 本 API 对外可访问的地址（公网 IP 或域名），部署时设置
    APP_PORT,                 # 本 API 的监听端口
)
# 日志级别: DEBUG / INFO / WARNING / ERROR
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
# 设为 0 可禁用 /docs 和 /redoc
ENABLE_DOCS = os.getenv("ENABLE_DOCS", "1") == "1"

# 可用仿真脚本（本地兜底列表）。实际列表以后端 get_script_list 为准
# （/scripts 与 /start、/reset 校验都会先拉取后端），后端不可达时回退到本列表。
AVAILABLE_SCRIPTS: List[str] = [
    "测试用例1",
]
# 环境变量可追加脚本名（逗号分隔）：后端 sces.json 新条目尚未生效时的补充手段
EXTRA_SCRIPTS: List[str] = [
    s.strip() for s in os.getenv("EXTRA_SCRIPTS", "").split(",") if s.strip()
]
# 默认脚本
DEFAULT_SCRIPT = "测试用例1"

# 宏观步步长（仿真秒数），即两次 Agent 决策之间推进的仿真时间
# 仿真速率约 100x，30 仿真秒 ≈ 0.3 真实秒，对 Agent 决策无感知延迟
MACRO_STEP_DURATION = float(os.getenv("MACRO_STEP", "30"))


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


def _grpc_call(func_name: str, kwargs: Optional[dict] = None,
               engine_name: Optional[str] = None):
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
    grpc_msg = MsgStr()
    setattr(grpc_msg, "msg", msg)
    return _grpc_stub().control(grpc_msg)


def _fetch_script_list() -> Optional[List[str]]:
    """从后端拉取仿真脚本列表（get_script_list 返回脚本树 JSON）。

    扁平化提取全部 value 叶节点；后端不可达、解析失败或返回异常时
    返回 None，调用方回退到本地 AVAILABLE_SCRIPTS + EXTRA_SCRIPTS。
    """
    try:
        resp = _grpc_call("get_script_list", kwargs={}, engine_name="")
        if resp.msg != "FUNC_SUCCESS" or not resp.data:
            _log.warning("get_script_list 返回 %s", resp.msg)
            return None
        tree = json.loads(resp.data)
    except Exception as e:
        _log.warning("拉取后端脚本列表失败: %s", e)
        return None

    names: List[str] = []

    def _walk(node) -> None:
        if isinstance(node, list):
            for x in node:
                _walk(x)
        elif isinstance(node, dict):
            # 节点两种形态: {"label","value","children":[...]} 或叶子 {"label","value"}
            val = node.get("value")
            if val and not node.get("children"):
                names.append(str(val))
            _walk(node.get("children"))

    _walk(tree)
    return names


def _known_scripts() -> List[str]:
    """当前可启动的脚本名: 后端列表优先，失败回退本地（含 EXTRA_SCRIPTS 补充）"""
    fetched = _fetch_script_list()
    names = list(fetched) if fetched is not None else list(AVAILABLE_SCRIPTS)
    for s in EXTRA_SCRIPTS:
        if s not in names:
            names.append(s)
    return names
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
    summary: Optional[dict] = Field(
        None,
        description="决策摘要（如每单位状态、上一步动作结果），仅记录进对局日志，不影响执行",
    )


# ╔══════════════════════════════════════════════════════════╗
# ║                     全局对局状态                          ║
# ╚══════════════════════════════════════════════════════════╝

@dataclass
class EpisodeState:
    """对局级状态，封装所有跨请求的全局变量"""
    engine_name: str = ""
    episode_id: int = 0
    script_name: str = ""               # 当前对局使用的脚本/方案名（随 /start、/reset 选定）
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
    decision_summary: dict = field(default_factory=dict)    # 决策摘要（决策方随 /apply 附带）


@dataclass
class GameLog:
    """一场对局的完整日志，用于 Agent 训练和行为分析"""
    episode_id: int
    script_name: str
    start_real_time: str = ""
    end_real_time: Optional[str] = None
    result: Optional[str] = None
    result_reason: Optional[str] = None
    closed_by: str = ""                                    # 文件封存原因: 对局结束/对局停止/对局重置
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
            "closed_by": self.closed_by,
            "total_steps": len(self.steps),
            "steps": [asdict(s) for s in self.steps],
            "final_stats": self.final_stats,
        }


_game_log: Optional[GameLog] = None
_game_log_snap_steps: int = 0      # GET /game_log 快照落盘时的步数水位（避免每步重复写盘）

# 合并格式对局日志（给人/LLM 阅读的追加式文本）：
# 每局一节，节首 episode=N，节尾 RESET 分割；外层为该局数据与结果，
# 内嵌"动作:"块按 step 列出局内单位动作（空操作/飞行等，带单位名称、速度、航向）。
_GAME_RECORDS_PATH = os.path.join(_GAME_LOG_DIR, "game_records.log")


def _init_game_log(script_name: str):
    """开始新对局时初始化日志。

    若上一局日志尚未封存（对局中途 reset），先落盘再开新文件——
    以 reset 为分割，每局一个文件，全部保留（人工清理）。
    """
    global _game_log, _game_log_snap_steps
    _save_game_log(closed_by="对局重置")
    _game_log = GameLog(
        episode_id=_state.episode_id,
        script_name=script_name,
        start_real_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    _game_log_snap_steps = 0


def _snapshot_game_log() -> Optional[str]:
    """把当前对局日志快照落盘到 logs/games/（GET /game_log 时调用）。

    快照不封存对局（不影响 stop/reset/结束时封存文件）；仅在步数比
    上次快照多时写盘。返回快照文件路径；无新内容时返回 None。
    """
    global _game_log_snap_steps
    if _game_log is None or not _game_log.steps:
        return None
    if len(_game_log.steps) <= _game_log_snap_steps:
        return None
    _game_log_snap_steps = len(_game_log.steps)
    snap_path = os.path.join(
        _GAME_LOG_DIR,
        f"game_{_game_log.episode_id}_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_snap.json")
    try:
        with open(snap_path, "w", encoding="utf-8") as f:
            json.dump(_game_log.to_dict(), f, ensure_ascii=False, indent=2)
        _log.info("对局日志快照已保存: %s", snap_path)
        return snap_path
    except Exception as e:
        _log.error("对局日志快照保存失败: %s", e)
        return None


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


def _record_step(raw: dict, action_results: List[dict],
                 decision_summary: Optional[dict] = None):
    """记录一次 /apply 后的状态快照。decision_summary 为决策方附带的
    决策摘要（每单位状态、动作意图、上一步执行结果），供复盘。"""
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

    record = StepRecord(
        step=len(_game_log.steps) + 1,
        sim_time=engine_time,
        episode_time=_fmt_time(episode_elapsed),
        real_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        actions=action_results,
        usv_states=usv_summary,
        uav_states=uav_summary,
        active_enemies=intel["active"],
        decision_summary=decision_summary or {},
        passive_enemies=intel["passive"],
        reward=raw.get("env_score_flat", {}) or {},
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

    # 动作失败/跳过统计：跨全部步骤聚合（含决策摘要里附带的上一步完整结果），
    # 按失败原因归类，如 {"已摧毁": 3, "已在甲板上，请先起飞": 1}
    fail_stats: Dict[str, int] = {}
    for s in _game_log.steps:
        candidates = list(s.actions)
        candidates += s.decision_summary.get("previous_actions", [])
        for a in candidates:
            if a.get("成功") and not a.get("跳过"):
                continue
            detail = a.get("详情") or ""
            key = detail.split("失败: ", 1)[-1] if "失败: " in detail else (detail or "未知原因")
            fail_stats[key] = fail_stats.get(key, 0) + 1

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
        "action_fail_stats": fail_stats,
    }

    _save_game_log(closed_by="对局结束")


def _fmt_action_line(a: dict) -> str:
    """把日志中的动作记录规范化为一行单位动作:
    'white_uav1 飞行 速度=30.0 航向=0.0' / '空操作'；
    失败/跳过带 [失败]/[跳过] 标记。解析失败时保留原动作文本。"""
    text = (a.get("动作") or "").strip()
    if "空操作" in text or "noop" in text:
        line = "空操作"
    else:
        # 从动作文本推断类型（关键词互斥，起飞/降落先于飞行判定）
        if "移动" in text:
            action_type = "move"
        elif "起飞" in text:
            action_type = "launch_uav"
        elif "降落" in text:
            action_type = "land_uav"
        elif "锁定" in text:
            action_type = "lock"
        elif "飞行" in text:
            action_type = "fly"
        else:
            action_type = ""
        try:
            parsed = _parse_action_text(text, action_type)
        except ValueError:
            line = text
        else:
            u, act, p = parsed["unit"], parsed["action"], parsed["params"]
            if act == "move":
                line = f"{u} 移动 速度={p['target_speed']} 航向={p['target_course']}"
            elif act == "fly":
                line = f"{u} 飞行 速度={p['target_speed']} 航向={p['target_course']}"
            elif act == "launch_uav":
                line = f"{u} 从 {p['home']} 起飞 速度={p['target_speed']} 航向={p['target_course']}"
            elif act == "land_uav":
                line = f"{u} 降落到 {p['target']}"
            elif act == "lock":
                line = f"{u} 锁定 {p['target']}"
            else:
                line = text
    if a.get("跳过"):
        line += " [跳过]"
    elif not a.get("成功"):
        line += " [失败]"
    return line


def _append_game_records() -> None:
    """对局封存时把该局追加写进合并格式日志 logs/games/game_records.log。

    一份文件按 RESET 分割每局：节首 episode=N（编号随 /start 递增、/reset 归 1），
    外层为该局数据与结果，内嵌"动作:"块按 step 列出局内单位动作。
    仅在对局封存（结束/停止/重置）时追加，保证每节都是一局完整数据。
    """
    global _game_log
    if _game_log is None or not _game_log.steps:
        return
    g = _game_log
    lines = [
        f"episode={g.episode_id}",
        f"脚本={g.script_name or '-'}",
        f"开始时间={g.start_real_time}",
        f"结束时间={g.end_real_time or '-'}",
        f"对局结果={g.result or '未结束'}",
        f"结果说明={g.result_reason or '-'}",
    ]
    st = g.final_stats
    if st:
        lines.append(
            f"存活统计=无人艇 {st.get('usv_alive', 0)}/{st.get('usv_total', 0)}"
            f" | 无人机 {st.get('uav_alive', 0)}/{st.get('uav_total', 0)}")
        lines.append(
            f"敌方统计=雷达捕获 {st.get('enemy_radar', 0)}"
            f" | 被动告警 {st.get('enemy_passive', 0)}")
        lines.append(f"行动总数={st.get('action_total', 0)}")
    lines.append(f"总步数={len(g.steps)}")
    lines.append("动作:")
    for s in g.steps:
        lines.append(f"  step={s.step} 局内时间={s.episode_time}")
        if not s.actions:
            lines.append("    (无动作)")
        for a in s.actions:
            lines.append("    " + _fmt_action_line(a))
    lines.append("RESET")
    try:
        with open(_GAME_RECORDS_PATH, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        _log.info("对局已追加到合并日志: %s", _GAME_RECORDS_PATH)
    except Exception as e:
        _log.error("合并日志追加失败: %s", e)


def _save_game_log(closed_by: str = "") -> bool:
    """封存对局日志到磁盘（每局一个文件，文件名带时间戳，全部保留不覆盖）。

    closed_by 标记封存原因（对局结束/对局停止/对局重置）。
    已封存过或尚无步数的不落盘，避免 stop+reset 重复写文件。
    """
    global _game_log
    if _game_log is None or _game_log.closed_by or not _game_log.steps:
        return False
    if closed_by:
        _game_log.closed_by = closed_by
    log_path = os.path.join(
        _GAME_LOG_DIR,
        f"game_{_game_log.episode_id}_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.json")
    try:
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(_game_log.to_dict(), f, ensure_ascii=False, indent=2)
        _append_game_records()   # 同步追加合并格式日志（RESET 分割，人/LLM 阅读）
        _log.info("对局日志已保存: %s (%s)", log_path, _game_log.closed_by)
    except Exception as e:
        _log.error("对局日志保存失败: %s", e)
    return True


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
                if not usv.get("is_alive"):
                    continue
                # 甲板占用检查
                deck_occupied = any(
                    u2.get("is_at_usv") and u2.get("home_name") == usv["name"]
                    for u2 in uavs if u2.get("name") != u["name"]
                )
                if deck_occupied:
                    continue
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

from pomdp_api.checks import check_move, check_fly, check_lock, check_launch_uav, check_land_uav


# ╔══════════════════════════════════════════════════════════╗
# ║              动作执行（check → engine → 反馈）           ║
# ╚══════════════════════════════════════════════════════════╝

def _execute_one_action(parsed: dict) -> dict:
    """执行单个动作

    流程: 查 state → check_xxx(raw) → engine 执行 → 反馈结果
    Returns:
        {"ok": bool, "skipped": bool, "detail": str}
    """
    a = parsed["action"]
    p = parsed["params"]
    unit = parsed["unit"]

    # 统一获取仿真状态，供所有 check 使用
    try:
        raw = _fetch_raw_state()
        intel = _build_enemy_intel(raw)
    except StateFetchError:
        raw = None
        intel = None

    try:
        if a == "noop":
            _log.info("空操作")
            return {"ok": True, "skipped": False, "detail": "空操作"}

        elif a == "move":
            fail = check_move(unit, raw)
            if fail: return fail
            spd = p.get("target_speed", 10.0)
            crs = p.get("target_course", 0.0)
            resp = _grpc_call("send_command", kwargs={"cmd": {
                "unit_name": unit, "target_speed": spd, "target_course": crs,
            }})
            ok = (resp.msg == "FUNC_SUCCESS")
            detail = f"{unit} 移动 speed={spd} course={crs}"
            if ok: _log.info(detail)
            else: detail += f" 失败: {resp.msg}"
            return {"ok": ok, "skipped": False, "detail": detail}

        elif a == "fly":
            fail = check_fly(unit, raw)
            if fail: return fail
            spd = p.get("target_speed", 10.0)
            crs = p.get("target_course", 0.0)
            resp = _grpc_call("send_command", kwargs={"cmd": {
                "unit_name": unit, "target_speed": spd, "target_course": crs,
            }})
            ok = (resp.msg == "FUNC_SUCCESS")
            detail = f"{unit} 飞行 speed={spd} course={crs}"
            if ok: _log.info(detail)
            else: detail += f" 失败: {resp.msg}"
            return {"ok": ok, "skipped": False, "detail": detail}

        elif a == "lock":
            target = p.get("target", "")
            fail = check_lock(unit, target, raw, intel)
            if fail: return fail
            # 引擎函数按平铺 kwargs 调用（sim_server: getattr(engine, func)(**kwargs)）
            resp = _grpc_call("cmd_lock", kwargs={
                "unit_name1": unit, "unit_name2": target,
            })
            ok = _parse_bool_result(resp)
            detail = f"{unit} 锁定 {target}"
            if ok: _log.info(detail)
            else: detail += f" 失败: {resp.msg}"
            return {"ok": ok, "skipped": False, "detail": detail}

        elif a == "launch_uav":
            home = p.get("home", "")
            fail = check_launch_uav(unit, home, raw)
            if fail: return fail
            spd = p.get("target_speed", 10.0)
            crs = p.get("target_course", 0.0)
            resp = _grpc_call("cmd_uav_takeoff", kwargs={
                "unit_name": unit, "home_name": home,
                "target_speed": spd, "target_course": crs,
            })
            ok = _parse_bool_result(resp)
            detail = f"{unit} 从 {home} 起飞 speed={spd} course={crs}"
            if ok: _log.info(detail)
            else: detail += f" 失败: {resp.msg}"
            return {"ok": ok, "skipped": False, "detail": detail}

        elif a == "land_uav":
            target = p.get("target", "")
            fail = check_land_uav(unit, target, raw)
            if fail: return fail
            resp = _grpc_call("cmd_uav_land", kwargs={
                "uav_name": unit, "usv_name": target,
            })
            ok = _parse_bool_result(resp)
            if ok:
                detail = f"{unit} 成功降落到 {target}"
                _log.info(detail)
            else:
                detail = f"{unit} 降落到 {target} 失败: 仿真后端拒绝"
                _log.warning(detail)
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
        if not alive_usvs and not alive_uavs:
            result = "Result.Defeat"
            reason = "我方所有单位被击毁"
        elif len(all_enemy_names) == 0:
            result = "Result.Victory"
            reason = "探测不到敌方单位"
        elif not alive_usvs:
            result = "Result.Defeat"
            reason = "我方所有无人艇被击毁"
        else:
            scores = raw.get("env_score_flat", {})
            if scores:
                total = sum(v for v in scores.values()
                           if isinstance(v, (int, float)))
                if total > 0:
                    result = "Result.Victory"
                    reason = f"综合得分为正: {total}"
                elif total < 0:
                    result = "Result.Defeat"
                    reason = f"综合得分为负: {total}"
                else:
                    result = "Result.Tie"
                    reason = "综合得分为零"
            else:
                result = "Result.Tie"
                reason = "我方有单位存活，无法判定明确胜负"

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

    # 若后端有残留引擎：引擎终止是异步的，强制终止后需等后端清空运行标志再重试
    for attempt in range(3):
        if resp.msg != "ENGINE_SIM_RUNNING":
            break
        _log.warning("ENGINE_SIM_RUNNING，强制终止后重试 (第%d次)", attempt + 1)
        try:
            _grpc_call("terminate", kwargs={}, engine_name="")
        except Exception:
            pass
        time.sleep(3)
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
