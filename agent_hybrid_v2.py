#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
agent_hybrid_v2.py — 白方通用海战 Agent V2（观测纯正、确定性执行核 + LLM Commander 战略层）
=============================================================================================

V2 在 V1（agent_hybrid_v1.py）之上叠加"低频率 LLM Commander"层，但**不替换**确定性执行核。

   HTTP observation
        ↓
   TrackManager                       ← 与 V1 相同（观测纯正、常量速度外推、置信度）
        ↓
   TacticalSummary                    ← 压缩 ~1-2k token 的战术摘要（不含敌方运行时真值）
        ↓
   LLM Commander (后台线程, 非阻塞)    ← 每 ≥600 仿真秒最多一次，异步调用 DeepSeek
        ↓
   StrategicIntent                    ← 结构化战略意图（posture/focus/reserve/uav_mode...）
        ↓
   ThreatAllocator / USVController / UAVManager   ← 与 V1 相同的确定性控制器（参数化）
        ↓
   ActionSafety                       ← 与 V1 相同（全部动作过 /legal_actions 校验）
        ↓
   /apply

LLM 只负责高层 posture / 威胁优先级 / 兵力集中度 / reserve / UAV 搜索重点 / 交战积极程度。
具体 USV move / lock / UAV fly / RTB / 电量 / 300s 锁计时 / 合法性过滤 仍由确定性控制器完成。

公平性铁律（最高优先级，勿违反，与 V1 相同）:
  # FAIR-PLAY RULE: 敌方运行时状态只能来自 HTTP 观测（/obs 语义文本 及 /status 中的
  #   观察信息.white_observation）。雷达捕获条目含 name/position/velocity —— 这就是
  #   引擎 get_white_targets 的"共享感知"输出）。
  # 禁止读取: engine.black_* / get_state().black_* / 固定敌方初始坐标 / 固定敌方
  #   数量 / 固定敌方速度(如 vx=-10) / black_strategy / 直接连接仿真器内部 gRPC。
  # 敌方全部运动学（数量、位置、速度、航向）必须从观测在线推断，不做先验假设。
  # TacticalSummarizer 只打包 /status 白名单字段 + TrackManager 历史航迹，绝不打
  # 包任何 black_* 运行时真相。

新增 Commander 相关:
  SkillLoader           读取 skills/maritime_commander/SKILL.md（启动时一次，失败用 fallback）
  TacticalSummarizer    压缩战术摘要（~1-2k token），只含公平信息
  StrategicIntent       LLM 输出的结构化战略意图（dataclass + schema 校验）
  CommanderIntentAdapter JSON parse / clamp / 无效 track 删除 / last-valid 兜底
  LLMCommander          后台线程 + 锁，异步请求，绝不阻塞实时主循环

环境变量:
  LLM_ENABLED=true/false    (默认 true)。为 false 时完全退化为 V1 确定性 + DEFAULT_INTENT。
  ANTHROPIC_BASE_URL / ANTHROPIC_AUTH_TOKEN / ANTHROPIC_MODEL  复用 agent_llm.py 已验证配置

用法:
  python agent_hybrid_v2.py                  # 正常对局（启用 UAV + LLM Commander）
  python agent_hybrid_v2.py --no-uav         # USV-only 模式
  python agent_hybrid_v2.py --selftest       # TrackManager 单测（离线 mock）
  python agent_hybrid_v2.py --mocktest       # Commander 层单测（离线 mock，不需要服务器）
"""
import os
import sys
import json
import math
import time
import threading
import requests

# ════════════════════════════════════════════════════════════════
# 常量与全局参数（与 V1 相同 + Commander 参数）
# ════════════════════════════════════════════════════════════════
API = "http://127.0.0.1:8000"
HTTP_TIMEOUT = 20

USV_SPEED = 20.0          # 白USV最大/巡航速度 m/s
UAV_FLY_SPEED = 100.0     # /fly schema 允许的最大速度（可执行上限）
UAV_GUIDE_SPEED = 50.0    # API land_uav 自动制导速度
LOCK_RANGE = 40_000.0     # 锁距 <40km
BREAKTHROUGH_X = 50_000.0 # 蓝方突破线 x≤50000 即失败
EMERGENCY_3V1_X = 150_000.0  # 敌x低于此值且已有2攻击者 → 派第3艘
FROZEN_DURATION = 300.0   # 命中冻结时长(s) —— 仅用于逻辑说明

# 航迹置信度参数
HIGH_CONF_AGE = 30.0      # 30s 内 → 高置信(可见)
EST_CONF_AGE = 120.0      # 30-120s → 估计置信
DROP_AGE = 180.0          # >180s 未看到 → 丢弃
CORPSE_AGE = 600.0        # 尸体检测: 被锁定位置持续>600s不变 → 已击沉

# UAV 电量安全
UAV_BATTERY_TOTAL = 25_000.0
UAV_SAFETY_MARGIN = 300.0
UAV_RECHARGE_THRESHOLD = 0.80
UAV_RTB_RANGE_KM = 2_000.0
SEARCH_X_MIN = 140_000.0
SEARCH_X_MAX = 260_000.0

# ── LLM Commander 参数 ──
SIM_RATE = 50.0                    # simulator 约 50× real-time
MIN_COMMANDER_INTERVAL_SIM = 600.0 # 两次 commander 请求最小间隔（仿真秒）
COMMANDER_TIMEOUT_S = 60           # LLM 单次调用超时（真实秒）
SKILL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "skills", "maritime_commander", "SKILL.md")

LOG_INTERVAL = 10          # 每 N 步打印聚合信息块


# ════════════════════════════════════════════════════════════════
# HTTP 客户端（复用自 agent_llm.py / agent_hybrid_v1.py 的稳定实现）
# ════════════════════════════════════════════════════════════════
def api(method, path, **kw):
    try:
        r = requests.request(method, f"{API}{path}", json=kw.get("json"),
                             params=kw.get("params"), timeout=HTTP_TIMEOUT)
        if r.status_code == 200:
            ct = r.headers.get("content-type", "")
            return r.json() if "application/json" in ct else r.text
        return None
    except Exception as e:
        print(f"  [HTTP] {method} {path} 异常: {e}")
        return None


class ApiClient:
    """封装 5 个核心端点，返回结构化数据"""

    def __init__(self, script_name=None):
        # 规模脚本通过环境变量 SCENARIO_SCRIPT 选择（如 scenario_10v10），
        # 默认保持向后兼容（测试用例1 = 原始 30v30）。
        self.script_name = script_name or os.getenv("SCENARIO_SCRIPT", "测试用例1")

    def start(self):
        return api("POST", "/start", params={"script_name": self.script_name})

    def status(self):
        return api("GET", "/status")

    def obs(self):
        return api("GET", "/obs")

    def legal_actions(self):
        return api("GET", "/legal_actions")

    def apply(self, actions):
        return api("POST", "/apply", json={"actions": actions})

    def stop(self):
        return api("GET", "/stop")

    def result(self):
        return api("GET", "/result")


# ════════════════════════════════════════════════════════════════
# 通用工具
# ════════════════════════════════════════════════════════════════
def bearing_to(frm, to):
    """frm -> to 的航向角，正北为0°，顺时针为正。"""
    dx, dy = to[0] - frm[0], to[1] - frm[1]
    return math.degrees(math.atan2(dx, dy)) % 360.0


def hdist(a, b):
    """水平距离（忽略z）"""
    return math.hypot(a[0] - b[0], a[1] - b[1])


def parse_sim_time(hm):
    """'HH:MM:SS' -> 秒"""
    try:
        hh, mm, ss = [int(x) for x in str(hm).split(":")]
        return hh * 3600 + mm * 60 + ss
    except Exception:
        return 0.0


# ════════════════════════════════════════════════════════════════
# 观测解析 —— 只从 /status JSON 提取公平信息（与 V1 相同）
# ════════════════════════════════════════════════════════════════
class Obs:
    """一次 /status 的结构化解析结果"""

    def __init__(self, status, now):
        self.now = now                       # 仿真时刻(s)
        self.status = status or {}
        self.ended = bool(status.get("已结束", False)) if status else False
        self.result = status.get("对局结果") if status else None

        rs = (status or {}).get("资源快照", {}) or {}
        stats = rs.get("统计", {}) or {}
        self.usv_total = stats.get("usv_total", 0)
        self.usv_alive = stats.get("usv_alive", 0)
        self.uav_total = stats.get("uav_total", 0)
        self.uav_alive = stats.get("uav_alive", 0)
        self.uav_flying = stats.get("uav_flying", 0)
        self.enemy_visible = stats.get("enemy_visible", 0)

        unit = rs.get("单位状态", {}) or {}
        self.usvs = unit.get("white_usv_states", []) or []
        self.uavs = unit.get("white_uav_states", []) or []

        intel = (rs.get("观察信息", {}) or {}).get("white_observation", {}) or {}
        self.active = intel.get("雷达捕获", []) or []      # [{name, position, velocity}]
        self.passive = intel.get("被动告警", []) or []     # [{name, bearing, detected_by}]

        reward = (status or {}).get("奖励信号", {}) or {}
        self.black_killed = reward.get("black_killed", 0)
        self.black_hit = reward.get("black_hit", 0)
        self.white_ship_killed = reward.get("white_ship_killed", 0)
        self.white_uav_killed = reward.get("white_uav_killed", 0)
        self.black_breakthrough = reward.get("black_breakthrough", 0)


class LegalSet:
    """/legal_actions 的解析 + 查询结构（与 V1 相同）"""

    def __init__(self, legal):
        self.raw = legal or {}
        self.actions = {}
        acts = legal.get("动作", {}) if isinstance(legal, dict) else {}
        if isinstance(acts, dict):
            self.actions = acts

        self.moves = set()
        self.locks = set()        # (usv, target)
        self.launches = set()     # (uav, home)
        self.flys = set()
        self.lands = set()        # (uav, usv)

        for s in self.actions.get("[move]", []) or []:
            parts = s.split()
            if len(parts) >= 1:
                self.moves.add(parts[0])
        for s in self.actions.get("[lock]", []) or []:
            parts = s.split()
            if len(parts) >= 3:
                self.locks.add((parts[0], parts[2]))
        for s in self.actions.get("[launch_uav]", []) or []:
            parts = s.split()
            if len(parts) >= 3:
                self.launches.add((parts[0], parts[2]))
        for s in self.actions.get("[fly]", []) or []:
            parts = s.split()
            if len(parts) >= 1:
                self.flys.add(parts[0])
        for s in self.actions.get("[land_uav]", []) or []:
            parts = s.split()
            if len(parts) >= 3:
                self.lands.add((parts[0], parts[2]))

    def can_lock(self, usv, target):
        return (usv, target) in self.locks

    def can_launch(self, uav, home):
        return (uav, home) in self.launches

    def can_land(self, uav, usv):
        return (uav, usv) in self.lands

    def can_move(self, usv):
        return usv in self.moves

    def can_fly(self, uav):
        return uav in self.flys


# ════════════════════════════════════════════════════════════════
# TrackManager —— 敌情航迹（与 V1 相同，观测纯正）
# ════════════════════════════════════════════════════════════════
class EnemyTrack:
    __slots__ = ("name", "last_position", "last_velocity", "last_seen_time",
                 "first_seen_time", "confidence", "has_position", "bearing",
                 "engaged", "assigned_usvs", "seen_count", "last_moved_time")

    def __init__(self, name, now):
        self.name = name
        self.last_position = None        # (x, y)
        self.last_velocity = None        # (vx, vy)
        self.last_seen_time = now
        self.first_seen_time = now
        self.confidence = 1.0
        self.has_position = False
        self.bearing = None              # 仅被动告警
        self.engaged = False             # 有≥1艘我方USV正在锁定
        self.assigned_usvs = set()
        self.seen_count = 1
        self.last_moved_time = now       # 最近一次观测到位置变化的时间(尸体检测)

    def update_obs(self, pos, vel, now):
        if pos is not None and len(pos) >= 2:
            if self.last_position is not None:
                dx = pos[0] - self.last_position[0]
                dy = pos[1] - self.last_position[1]
                if dx * dx + dy * dy > 25.0:   # >5m 视为发生了移动
                    self.last_moved_time = now
            else:
                self.last_moved_time = now
            self.last_position = (pos[0], pos[1])
            self.has_position = True
        if vel is not None and len(vel) >= 2:
            self.last_velocity = (vel[0], vel[1])
        self.last_seen_time = now
        self.confidence = 1.0   # 重新看到即恢复高置信
        self.seen_count += 1

    def stationary_duration(self, now):
        """位置持续不变的时间(s)。冻结上限300s, 持续>CORPSE_AGE即尸体。"""
        return now - self.last_moved_time

    def age(self, now):
        return now - self.last_seen_time

    def is_visible(self, now):
        return self.age(now) < HIGH_CONF_AGE

    def predicted_position(self, now):
        """常量速度外推"""
        if self.last_position is None:
            return None
        if self.last_velocity is None:
            return self.last_position
        dt = now - self.last_seen_time
        return (self.last_position[0] + self.last_velocity[0] * dt,
                self.last_position[1] + self.last_velocity[1] * dt)


class TrackManager:
    """维护所有已知敌舰航迹。与 V1 相同。"""

    def __init__(self):
        self.tracks = {}          # name -> EnemyTrack
        self.killed_names = set() # 已判定击沉的敌名(防止死灰复燃)

    def update(self, obs):
        now = obs.now
        events = []
        seen = set()

        for e in obs.active:
            name = e.get("name", "")
            if not name:
                continue
            if name in self.killed_names:
                continue
            pos = e.get("position")
            vel = e.get("velocity")
            seen.add(name)
            if name not in self.tracks:
                self.tracks[name] = EnemyTrack(name, now)
                events.append(("DETECT", name))
            self.tracks[name].update_obs(pos, vel, now)

        for p in obs.passive:
            name = p.get("name", "")
            if not name or name in seen:
                continue
            seen.add(name)
            if name not in self.tracks:
                t = EnemyTrack(name, now)
                t.bearing = p.get("bearing")
                self.tracks[name] = t
                events.append(("DETECT", name))

        to_drop = []
        for name, t in self.tracks.items():
            if name in seen:
                continue
            age = t.age(now)
            if age >= DROP_AGE:
                to_drop.append(name)
            elif age >= HIGH_CONF_AGE:
                t.confidence = 0.5
            else:
                t.confidence = 1.0
        for name in to_drop:
            del self.tracks[name]

        return events

    def reconcile_assigned(self, obs, usv_targets=None):
        for t in self.tracks.values():
            t.assigned_usvs = set()
            t.engaged = False
        for u in obs.usvs:
            if not u.get("is_alive"):
                continue
            lu = u.get("locking_unit")
            if lu and lu in self.tracks:
                self.tracks[lu].assigned_usvs.add(u["name"])
                self.tracks[lu].engaged = True
            elif lu:
                if lu not in self.tracks and lu not in self.killed_names:
                    t = EnemyTrack(lu, obs.now)
                    t.confidence = 0.5
                    self.tracks[lu] = t
        if usv_targets:
            for uname, tname in usv_targets.items():
                if not tname or tname not in self.tracks:
                    continue
                if uname in self.tracks[tname].assigned_usvs:
                    continue
                self.tracks[tname].assigned_usvs.add(uname)

    def kill_detect(self, obs, prev_black_killed):
        killed = []
        now = obs.now
        delta = obs.black_killed - prev_black_killed
        active_names = {e.get("name") for e in obs.active}
        engaged_missing = []
        for name, t in self.tracks.items():
            if not t.engaged or name in active_names:
                continue
            if t.engaged and name not in active_names:
                engaged_missing.append(name)
        if delta > 0:
            engaged_missing.sort(key=lambda n: -len(self.tracks[n].assigned_usvs))
            for name in engaged_missing[:delta]:
                killed.append(name)
        for name, t in self.tracks.items():
            if name in killed or not t.has_position:
                continue
            if t.stationary_duration(now) >= CORPSE_AGE:
                killed.append(name)
        for name in dict.fromkeys(killed):
            self.killed_names.add(name)
            del self.tracks[name]
        return [("KILL", name) for name in dict.fromkeys(killed)], list(dict.fromkeys(killed))

    def lost_high_threat(self, now, max_age=EST_CONF_AGE):
        out = []
        for t in self.tracks.values():
            if not t.has_position or t.is_visible(now):
                continue
            age = t.age(now)
            if age >= max_age:
                continue
            if t.confidence >= 0.5:
                out.append(t)
        return out


# ════════════════════════════════════════════════════════════════
# StrategicIntent —— LLM Commander 的结构化战略意图（经 adapter clamp）
# ════════════════════════════════════════════════════════════════
class StrategicIntent:
    """战略级意图。只调整资源/姿态，不产生任何具体动作。

    字段（与 schema 一致）:
      posture:              cautious | balanced | aggressive
      focus_level:          1~3      常规交战每目标攻击者数
      emergency_focus_level:2~4      临近突破高威胁的攻击者数
      reserve_ratio:        0.0~0.5  预备比例 = 预备USV / 当前可用USV（规模无关，
                                     敌情不明时高、临近突破时低；默认 0.20）
      reserve_usvs:         显式绝对预备数（旧字段，None = 用 reserve_ratio 计算）
      threat_bias:          breakthrough_eta | nearest | highest_confidence | balanced
      priority_tracks:      TrackManager 中当前存在的 track 名列表（轻量优先级加分）
      uav_mode:             broad_search | search_and_reacquire | focused_reacquire
      uav_priority_tracks:  优先 reacquire 的 track 名列表
      recon_aggressiveness: 0~1      侦察投入程度
      engagement_aggressiveness: 0~1 交战积极程度
      reason:               短文本，仅日志
    """
    __slots__ = ("posture", "focus_level", "emergency_focus_level", "reserve_usvs",
                 "reserve_ratio", "threat_bias", "priority_tracks", "uav_mode",
                 "uav_priority_tracks", "recon_aggressiveness",
                 "engagement_aggressiveness", "reason")

    def __init__(self, posture="balanced", focus_level=2, emergency_focus_level=3,
                 reserve_usvs=None, reserve_ratio=0.20,
                 threat_bias="breakthrough_eta", priority_tracks=None,
                 uav_mode="search_and_reacquire", uav_priority_tracks=None,
                 recon_aggressiveness=0.6, engagement_aggressiveness=0.7, reason=""):
        self.posture = posture
        self.focus_level = int(focus_level)
        self.emergency_focus_level = int(emergency_focus_level)
        self.reserve_usvs = int(reserve_usvs) if reserve_usvs is not None else None
        self.reserve_ratio = max(0.0, min(0.5, float(reserve_ratio)))
        self.threat_bias = threat_bias
        self.priority_tracks = list(priority_tracks or [])
        self.uav_mode = uav_mode
        self.uav_priority_tracks = list(uav_priority_tracks or [])
        self.recon_aggressiveness = float(recon_aggressiveness)
        self.engagement_aggressiveness = float(engagement_aggressiveness)
        self.reason = reason or ""

    def describe(self):
        resv = self.reserve_usvs if self.reserve_usvs is not None else "auto"
        return (f"posture={self.posture} focus={self.focus_level} "
                f"emergency={self.emergency_focus_level} reserve_ratio={self.reserve_ratio:.2f} "
                f"reserve_usvs={resv} "
                f"bias={self.threat_bias} priority={self.priority_tracks} "
                f"uav_mode={self.uav_mode} uav_priority={self.uav_priority_tracks} "
                f"recon={self.recon_aggressiveness:.1f} engage={self.engagement_aggressiveness:.1f}")

    def __eq__(self, other):
        return (isinstance(other, StrategicIntent)
                and self.posture == other.posture
                and self.focus_level == other.focus_level
                and self.emergency_focus_level == other.emergency_focus_level
                and self.reserve_usvs == other.reserve_usvs
                and abs(self.reserve_ratio - other.reserve_ratio) < 1e-9
                and self.threat_bias == other.threat_bias
                and self.priority_tracks == other.priority_tracks
                and self.uav_mode == other.uav_mode
                and self.uav_priority_tracks == other.uav_priority_tracks
                and abs(self.recon_aggressiveness - other.recon_aggressiveness) < 1e-9
                and abs(self.engagement_aggressiveness - other.engagement_aggressiveness) < 1e-9)

    def __repr__(self):
        return f"StrategicIntent({self.describe()})"


# LLM 不可用 / 首次失败 / LLM_ENABLED=false 时使用的默认意图
DEFAULT_INTENT = StrategicIntent()


# ════════════════════════════════════════════════════════════════
# SkillLoader —— 加载 Maritime Commander Skill（启动时一次）
# ════════════════════════════════════════════════════════════════
class SkillLoader:
    """读取 skills/maritime_commander/SKILL.md。

    失败时使用内置最小 fallback doctrine，绝不导致 Agent 崩溃。
    Skill 只保存长期稳定作战知识，不含任何某一局实时状态。
    """

    FALLBACK_DOCTRINE = (
        "Maritime Commander minimal fallback doctrine:\n"
        "USVs are the primary combat platform. Focus fire beats 1v1; 2v1 is the default "
        "cooperative engagement, 3v1 for urgent high threats near the breakthrough line.\n"
        "Keep a small reserve when the enemy picture is incomplete; relax it when a "
        "breakthrough threat is imminent.\n"
        "UAVs are recon/sensing assets, not combat platforms: search unknown areas and "
        "reacquire high-threat lost tracks; battery and RTB are managed deterministically.\n"
        "Commander outputs strategic intent only, inferred from observation. Never assume "
        "enemy count, position, velocity, or script a priori."
    )

    def __init__(self, path=SKILL_PATH):
        self.path = path
        self.text = None

    def load(self):
        """读取一次并缓存文本；失败返回内置 fallback。"""
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self.text = f.read()
        except Exception:
            self.text = self.FALLBACK_DOCTRINE
        return self.text


# ════════════════════════════════════════════════════════════════
# LLM API（复用 agent_llm.py 已验证的 DeepSeek/Anthropic 兼容调用）
# ════════════════════════════════════════════════════════════════
DS_URL = os.getenv("ANTHROPIC_BASE_URL", "https://api.deepseek.com/anthropic") + "/v1/messages"
DS_KEY = os.getenv("ANTHROPIC_AUTH_TOKEN", "")
DS_MODEL = os.getenv("ANTHROPIC_MODEL", "deepseek-v4-flash")


def call_commander_llm(system, user, timeout=COMMANDER_TIMEOUT_S):
    """调用 LLM，返回纯文本响应；失败返回 None。

    复用 agent_llm.py 已验证的模式：
      - Anthropic-compatible /v1/messages 端点
      - thinking disabled（避免 thinking token 占满输出）
    """
    payload = {
        "model": DS_MODEL,
        "max_tokens": 2000,
        "thinking": {"type": "disabled"},  # 禁用思考, 直接输出 text
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    try:
        resp = requests.post(DS_URL, headers={
            "x-api-key": DS_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }, json=payload, timeout=timeout)
        if resp.status_code != 200:
            return None
        data = resp.json()
        return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    except Exception:
        return None


# ════════════════════════════════════════════════════════════════
# Commander prompt —— role + skill + output schema
# ════════════════════════════════════════════════════════════════
COMMANDER_ROLE = """你是 Maritime Fleet Commander。
你不直接控制舰艇。
你的任务是根据当前有限观测的战术摘要，给底层 deterministic controllers 提供战略级资源配置建议。
你必须遵守 Maritime Commander Skill。
你不知道敌方当前使用哪个 script，不能假设固定敌人数量、位置、航向或策略。
不要输出 move / lock / fly 等具体动作。
只输出符合 schema 的 JSON StrategicIntent。
你的建议会被 deterministic controller 和 safety layer 校验。

目标优先级：
1. 防止突破
2. 降低高威胁目标
3. 建立局部兵力优势
4. 保留必要侦察与预备力量
5. 避免无意义地把全部兵力同时 commit

在不确定敌情下：不要把预测当成真值。
对低 confidence lost track：优先考虑 UAV reacquire，而不是直接大量投入 USV。
对已经稳定 engagement 的目标：不要无意义重新分配已锁 USV。

只输出 JSON，不要 markdown。"""

INTENT_SCHEMA_DOC = """输出 JSON StrategicIntent，字段与约束：
{
  "posture": "balanced",                 // cautious | balanced | aggressive
  "focus_level": 2,                      // int 1~3（常规交战每目标攻击者数）
  "emergency_focus_level": 3,            // int 2~4（临近突破高威胁的攻击者数）
  "reserve_ratio": 0.20,                 // float 0~0.5（预备比例 = 预备USV/当前可用USV；
                                         //   规模无关：敌情不明时高，临近突破时可降到 0）
  "threat_bias": "breakthrough_eta",     // breakthrough_eta | nearest | highest_confidence | balanced
  "priority_tracks": ["E3","E7"],        // 只能是 CURRENT TACTICAL STATE 中当前存在的 track id
  "uav_mode": "search_and_reacquire",    // broad_search | search_and_reacquire | focused_reacquire
  "uav_priority_tracks": ["E7"],         // 只能是当前存在的 track id
  "recon_aggressiveness": 0.7,           // 0~1（侦察投入程度）
  "engagement_aggressiveness": 0.7,      // 0~1（交战积极程度）
  "reason": "短文本，仅日志用"
}
注意：
- priority_tracks / uav_priority_tracks 只能选战术摘要中出现的 track 名；无重点可给空数组。
- 输出必须是合法 JSON 对象，不要 markdown 围栏，不要解释。"""


# ════════════════════════════════════════════════════════════════
# CommanderIntentAdapter —— LLM 输出的确定性 clamp / 校验
# ════════════════════════════════════════════════════════════════
class CommanderIntentAdapter:
    """把 LLM 文本解析为 StrategicIntent。

    - JSON parse（容错 markdown 围栏 / 前缀）
    - schema 校验 + 数值 clamp
    - 删除不存在的 track id
    - 任何失败返回 (None, reason) → 调用方使用 last_valid_intent / DEFAULT_INTENT
    """

    POSTURES = {"cautious", "balanced", "aggressive"}
    BIASES = {"breakthrough_eta", "nearest", "highest_confidence", "balanced"}
    UAV_MODES = {"broad_search", "search_and_reacquire", "focused_reacquire"}

    @staticmethod
    def extract_json_object(text):
        """从 LLM 输出中提取第一个平衡的 JSON 对象（容忍 markdown 围栏/前后缀）。"""
        if not text:
            return None
        s = text.strip()
        if s.startswith("```"):
            s = s.split("```", 2)[1] if s.count("```") >= 2 else s
            nl = s.find("\n")
            if nl != -1:
                s = s[nl + 1:]
        start = s.find("{")
        if start == -1:
            return None
        depth, in_str, esc = 0, False, False
        for i in range(start, len(s)):
            c = s[i]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
                continue
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(s[start:i + 1])
                    except Exception:
                        return None
        return None

    @staticmethod
    def parse(text, valid_tracks):
        obj = CommanderIntentAdapter.extract_json_object(text)
        if obj is None:
            return None, "malformed_json"
        return CommanderIntentAdapter.validate(obj, valid_tracks)

    @staticmethod
    def validate(obj, valid_tracks):
        valid_tracks = set(valid_tracks or [])
        try:
            posture = str(obj.get("posture", "balanced")).strip().lower()
            if posture not in CommanderIntentAdapter.POSTURES:
                posture = "balanced"
            focus = max(1, min(3, int(obj.get("focus_level", 2))))
            emg = max(2, min(4, int(obj.get("emergency_focus_level", 3))))
            reserve_ratio = max(0.0, min(0.5, float(obj.get("reserve_ratio", 0.20))))
            _rv = obj.get("reserve_usvs")
            # 旧字段显式绝对预备数向后兼容；未给出则用 reserve_ratio
            reserve_usvs = max(0, min(8, int(_rv))) if _rv is not None else None
            bias = str(obj.get("threat_bias", "breakthrough_eta")).strip().lower()
            if bias not in CommanderIntentAdapter.BIASES:
                bias = "breakthrough_eta"
            uav_mode = str(obj.get("uav_mode", "search_and_reacquire")).strip().lower()
            if uav_mode not in CommanderIntentAdapter.UAV_MODES:
                uav_mode = "search_and_reacquire"
            recon = max(0.0, min(1.0, float(obj.get("recon_aggressiveness", 0.6))))
            engage = max(0.0, min(1.0, float(obj.get("engagement_aggressiveness", 0.7))))
            reason = str(obj.get("reason", ""))[:200]

            def clean(lst):
                out = []
                for n in (lst or []):
                    n = str(n).strip()
                    if n and n in valid_tracks and n not in out:
                        out.append(n)
                return out

            prio = clean(obj.get("priority_tracks"))
            uprio = clean(obj.get("uav_priority_tracks"))
        except Exception:
            return None, "invalid_values"

        intent = StrategicIntent(posture=posture, focus_level=focus,
                                 emergency_focus_level=emg, reserve_usvs=reserve_usvs,
                                 reserve_ratio=reserve_ratio,
                                 threat_bias=bias, priority_tracks=prio, uav_mode=uav_mode,
                                 uav_priority_tracks=uprio, recon_aggressiveness=recon,
                                 engagement_aggressiveness=engage, reason=reason)
        return intent, None


# ════════════════════════════════════════════════════════════════
# TacticalSummarizer —— 压缩战术摘要（不含 black runtime truth）
# ════════════════════════════════════════════════════════════════
class TacticalSummarizer:
    """把 /status 公平字段 + TrackManager 航迹压缩为 ~1-2k token 的摘要。

    只打包：
      - friendly state（/status 白名单）
      - TrackManager 维护的历史航迹（观测位置/速度/置信度/威胁/分配）
    绝不读取任何 black_* 运行时真相。
    """

    def __init__(self, allocator):
        self.allocator = allocator

    def build(self, obs, tracker, usv_ctrl, uav_mgr, intent):
        now = obs.now
        usv_st = usv_ctrl.state
        n_avail = sum(1 for s in usv_st.values() if s == USVController.AVAILABLE)
        n_lock = sum(1 for s in usv_st.values() if s == USVController.LOCKING)
        n_frz = sum(1 for s in usv_st.values() if s == USVController.FROZEN)
        uav_st = uav_mgr.state
        n_air = sum(1 for v in uav_st.values() if v in (UAVManager.SEARCH, UAVManager.REACQUIRE))
        n_rtb = sum(1 for v in uav_st.values() if v == UAVManager.RETURN)
        n_chg = sum(1 for v in uav_st.values() if v in (UAVManager.CHARGING, UAVManager.LANDING))

        tracks = list(tracker.tracks.values())
        tracks.sort(key=lambda t: -self.allocator.threat_score(t, now))
        lost_ht = tracker.lost_high_threat(now)
        # 规模无关：航迹多时只 detail 威胁最高的 K 条，其余以聚合计数概括，
        # 保证 Commander 上下文在不同规模下保持 ~1-2k token 恒定。
        K = min(8, len(tracks))
        n_vis = sum(1 for t in tracks if t.is_visible(now))
        n_eng = sum(1 for t in tracks if t.engaged)
        n_un = sum(1 for t in tracks if t.has_position and not t.assigned_usvs)
        detail = tracks[:K]

        L = []
        L.append("TIME:")
        L.append(f"sim_time={int(now)}")
        L.append("")
        L.append("MISSION:")
        L.append("prevent breakthrough")
        L.append("")
        L.append("FRIENDLY:")
        L.append(f"usv_alive={obs.usv_alive} usv_available={n_avail} usv_engaged={n_lock} usv_frozen={n_frz}")
        L.append(f"uav_airborne={n_air + n_rtb} uav_searching={n_air} uav_returning={n_rtb} uav_charging={n_chg}")
        L.append("")
        L.append("KNOWN ENEMY TRACKS:")
        if not tracks:
            L.append("(none detected)")
        else:
            L.append(f"count={len(tracks)} visible={n_vis} lost={len(tracks) - n_vis} "
                     f"engaged={n_eng} unassigned={n_un}")
        for t in detail:
            pos = t.predicted_position(now) if t.has_position else None
            L.append(f"{t.name}:")
            L.append(f"  visible={str(t.is_visible(now)).lower()}")
            if pos is not None:
                L.append(f"  position=({int(pos[0])},{int(pos[1])})")
            else:
                L.append("  position=unknown")
            if t.last_velocity is not None:
                L.append(f"  velocity=({int(t.last_velocity[0])},{int(t.last_velocity[1])})")
            else:
                L.append("  velocity=unknown")
            L.append(f"  confidence={t.confidence:.2f}")
            L.append(f"  threat={self.allocator.threat_score(t, now):.2f}")
            L.append(f"  attackers={len(t.assigned_usvs)}")
            L.append(f"  engaged={str(t.engaged).lower()}")
        if len(tracks) > K:
            L.append(f"({len(tracks) - K} more tracks not detailed — see aggregate counts)")
        L.append("")
        L.append("TOP THREATS:")
        for i, t in enumerate(tracks[:K], 1):
            pos = t.predicted_position(now) if t.has_position else None
            xs = f" x={int(pos[0])}" if pos is not None else ""
            L.append(f"{i}. {t.name} threat={self.allocator.threat_score(t, now):.2f}{xs} "
                     f"attackers={len(t.assigned_usvs)}")
        L.append("")
        L.append("ENGAGEMENT:")
        L.append(f"targets_engaged={sum(1 for t in tracks if t.engaged)} "
                 f"targets_unassigned={sum(1 for t in tracks if t.has_position and not t.assigned_usvs)}")
        L.append("")
        L.append("RECON:")
        L.append(f"lost_high_threat_tracks={len(lost_ht)}")
        L.append(f"uav_coverage_summary=airborne={n_air + n_rtb} searching={n_air} returning={n_rtb} charging={n_chg}")
        L.append("")
        L.append("CURRENT COMMANDER INTENT:")
        L.append(intent.describe())
        return "\n".join(L), [t.name for t in tracks]


# ════════════════════════════════════════════════════════════════
# LLMCommander —— 后台异步 commander（绝不阻塞实时主循环）
# ════════════════════════════════════════════════════════════════
class LLMCommander:
    """后台线程 + 锁。主循环每步调用 maybe_request()；若满足间隔且无 in-flight，
    则快照当前摘要交给后台线程调 LLM，完成后原子更新 latest_intent。
    主循环始终使用 last_valid intent（get_intent()），绝不等待 LLM。
    """

    def __init__(self, enabled=True, skill_text=None, min_interval_sim=MIN_COMMANDER_INTERVAL_SIM,
                 call_fn=None):
        self.enabled = enabled
        self.lock = threading.Lock()
        self.latest_intent = DEFAULT_INTENT
        self.last_request_sim = float("-inf")
        self.in_flight = False
        self.min_interval_sim = min_interval_sim
        self.skill_text = skill_text or SkillLoader.FALLBACK_DOCTRINE
        self.call_fn = call_fn or call_commander_llm
        self.stats = {"calls": 0, "responses": 0, "parse_failures": 0,
                      "api_failures": 0, "latency_sum": 0.0}

    def build_system_prompt(self):
        return "\n\n".join([
            COMMANDER_ROLE,
            "=== Maritime Commander Skill ===",
            self.skill_text,
            "=== Output Schema ===",
            INTENT_SCHEMA_DOC,
        ])

    def get_intent(self):
        with self.lock:
            return self.latest_intent

    def maybe_request(self, now_sim, summary_text, valid_tracks, trigger="periodic"):
        """由实时主循环调用。立即返回（spawn 后台线程），不阻塞。"""
        if not self.enabled:
            return False
        with self.lock:
            if self.in_flight:
                return False
            if now_sim - self.last_request_sim < self.min_interval_sim:
                return False
            self.in_flight = True
            self.last_request_sim = now_sim
        print(f"[COMMANDER REQUEST] t={now_sim:.0f}s trigger={trigger}")
        t = threading.Thread(target=self._worker,
                             args=(summary_text, list(valid_tracks), trigger),
                             daemon=True)
        t.start()
        return True

    def _worker(self, summary_text, valid_tracks, trigger):
        t0 = time.time()
        raw = self._safe_call(summary_text)
        latency = time.time() - t0
        with self.lock:
            self.stats["calls"] += 1
            self.stats["latency_sum"] += latency
        if raw is None:
            with self.lock:
                self.stats["api_failures"] += 1
                self.in_flight = False
            print(f"[COMMANDER FALLBACK] reason=api_failure using=last_valid_intent "
                  f"latency_real={latency:.1f}s")
            return
        intent, err = CommanderIntentAdapter.parse(raw, valid_tracks)
        with self.lock:
            if intent is None:
                self.stats["parse_failures"] += 1
                self.in_flight = False
                print(f"[COMMANDER FALLBACK] reason=parse_error({err}) "
                      f"using=last_valid_intent latency_real={latency:.1f}s")
                return
            self.latest_intent = intent
            self.in_flight = False
            self.stats["responses"] += 1
        sim_equiv = latency * SIM_RATE
        print(f"[COMMANDER RESPONSE] {intent.describe()} reason={intent.reason!r} "
              f"latency_real={latency:.1f}s sim_equiv={sim_equiv:.0f}s")

    def _safe_call(self, summary_text):
        system = self.build_system_prompt()
        user = f"CURRENT TACTICAL STATE:\n\n{summary_text}\n\nReturn the next StrategicIntent."
        try:
            return self.call_fn(system, user)
        except Exception as e:
            print(f"[COMMANDER] LLM call exception: {e}")
            return None


# ════════════════════════════════════════════════════════════════
# ThreatAllocator —— 威胁评估 + 2v1/3v1 贪心分配（V1 逻辑 + intent 参数化）
# ════════════════════════════════════════════════════════════════
class ThreatAllocator:
    """对每个航迹计算威胁分，按威胁从高到低贪心分配可用的 USV。

    与 V1 的差异：接受 intent 参数化
      - focus_level / emergency_focus_level  控制常规/紧急每目标攻击者数
      - reserve_usvs                         保留预备 USV 不长途 commit（紧急时放松）
      - priority_tracks                      对重点目标加轻量优先级加分
      - threat_bias                          改变威胁分权重（突破ETA/最近/高置信/均衡）
      - engagement_aggressiveness            缩放"紧急3v1"触发距离
    """

    def threat_score(self, t, now, intent=None, usvs=None):
        pos = t.predicted_position(now)
        if pos is None:
            return 0.0
        x = pos[0]
        bias = "balanced"
        if intent is not None and getattr(intent, "threat_bias", None):
            bias = intent.threat_bias
        d_break = max(0.0, x - BREAKTHROUGH_X)
        prox = max(0.0, min(1.0, 1.0 - d_break / 200_000.0))
        # 向西速度(vx<0) → 威胁高。绝不假设固定速度，只用观测值
        vx = t.last_velocity[0] if t.last_velocity else 0.0
        vel = max(0.0, min(1.0, -vx / 20.0))
        conf = t.confidence
        focus = intent.focus_level if intent else 2
        alloc = max(0.0, (float(focus) - len(t.assigned_usvs)) / float(focus))
        if bias == "breakthrough_eta":
            w_prox, w_vel, w_conf = 1.9, 0.8, 1.0
        elif bias == "highest_confidence":
            w_prox, w_vel, w_conf = 1.4, 0.6, 1.8
        else:  # balanced / nearest
            w_prox, w_vel, w_conf = 1.4, 0.8, 1.0
        score = w_prox * prox + w_vel * vel + w_conf * conf + 0.8 * alloc
        if bias == "nearest" and usvs:
            nearest = float("inf")
            for u in usvs:
                if not u.get("is_alive") or not u.get("position"):
                    continue
                up = (u["position"][0], u["position"][1])
                d = math.hypot(up[0] - pos[0], up[1] - pos[1])
                if d < nearest:
                    nearest = d
            if nearest != float("inf"):
                near = max(0.0, min(1.0, 1.0 - nearest / 200_000.0))
                score += 0.8 * near
        if t.engaged:
            score += 0.2
        return score

    @staticmethod
    def _is_ship(name):
        # 胜利与突破只由敌舰决定；敌UAV是侦察机，击杀敌舰即可获胜。
        return "usv" in name

    def allocate_usvs(self, tracks, usvs, usv_map, now, intent=None):
        """需要USV位置时使用本函数(简单版, 直接用距离)。"""
        usv_pos = {u["name"]: (u["position"][0], u["position"][1])
                   for u in usvs if u.get("is_alive") and u.get("position")}
        available = [name for name, trg in usv_map.items()
                     if trg is None and name in usv_pos]

        focus = intent.focus_level if intent else 2
        emg = intent.emergency_focus_level if intent else 3
        agg = intent.engagement_aggressiveness if intent else 0.5
        emg_x = EMERGENCY_3V1_X * (0.5 + agg)   # 越积极，越早触发紧急 3v1

        scored = []
        for name, t in tracks.items():
            if not t.has_position or name in _KILLED:
                continue
            if not self._is_ship(name):
                continue
            cur = len(t.assigned_usvs)
            pos = t.predicted_position(now)
            want = 0
            if cur < focus:
                want = focus - cur
            elif cur < emg and pos is not None and pos[0] < emg_x:
                want = emg - cur
            if want > 0:
                score = self.threat_score(t, now, intent=intent, usvs=usvs)
                if intent and name in intent.priority_tracks:
                    score += 0.3   # 轻量优先级加分，不覆盖原威胁分
                scored.append((score, name, want, pos))
        scored.sort(key=lambda x: -x[0])

        # reserve：非紧急时按 reserve_ratio × 当前可用 USV 保留预备（规模无关）。
        # 紧急(有目标临近突破线) → 放松 reserve，把兵力压上。
        emergency = any(s[3] is not None and s[3][0] < emg_x for s in scored)
        reserve = 0
        if intent and not emergency:
            if intent.reserve_usvs is not None:
                # 旧字段显式绝对预备数（向后兼容）
                reserve = max(0, min(intent.reserve_usvs, len(available)))
            else:
                ratio = getattr(intent, "reserve_ratio", 0.20)
                reserve = int(round(len(available) * ratio))
                reserve = max(0, min(reserve, len(available)))
        if reserve and len(available) <= reserve:
            return {}          # 全部留作预备
        if reserve:
            available = available[:-reserve]

        result = {}
        for _, name, want, pos in scored:
            if not available:
                break
            pick = []
            while want > 0 and available:
                best, bestd = None, float("inf")
                for uname in available:
                    ux, uy = usv_pos[uname]
                    d = math.hypot(ux - pos[0], uy - pos[1]) if pos else 0.0
                    if d < bestd:
                        bestd, best = d, uname
                if best is None:
                    break
                available.remove(best)
                pick.append(best)
                want -= 1
            if pick:
                result[name] = pick
        return result


# 已判定击沉的敌舰名（AgentMain 每步更新）
_KILLED = set()


# ════════════════════════════════════════════════════════════════
# USVController —— USV 状态机 + 锁定逻辑（与 V1 相同）
# ════════════════════════════════════════════════════════════════
class USVController:
    """USV 状态: DEAD / FROZEN / LOCKING / INTERCEPTING / AVAILABLE

    铁律:
      - 分配保持: 已锁定目标绝不切换; 拦截中目标未失效也绝不切换
      - 锁定后保持 <40km(继续朝目标机动)
      - 被敌锁定不后撤(后撤=放弃我方锁定进度, 送死)
    """

    DEAD, FROZEN, LOCKING, INTERCEPTING, AVAILABLE = "DEAD", "FROZEN", "LOCKING", "INTERCEPTING", "AVAILABLE"

    def __init__(self):
        self.targets = {}        # usv_name -> track_name or None
        self.state = {}          # usv_name -> 状态名

    def classify(self, usv):
        if not usv.get("is_alive"):
            return self.DEAD
        if usv.get("is_frozen"):
            return self.FROZEN
        if usv.get("is_locking") and usv.get("locking_unit"):
            return self.LOCKING
        name = usv["name"]
        if self.targets.get(name):
            return self.INTERCEPTING
        return self.AVAILABLE

    def step(self, obs, tracks, legal, alloc_result, events):
        """返回 (actions, new_targets) 。new_targets 覆盖内部表并回写。"""
        actions = []
        new_targets = {}
        usv_pos = {}

        for u in obs.usvs:
            if not u.get("is_alive"):
                new_targets[u["name"]] = None
                self.state[u["name"]] = self.DEAD
                continue
            name = u["name"]
            pos = (u["position"][0], u["position"][1]) if u.get("position") else None
            usv_pos[name] = pos
            st = self.classify(u)
            self.state[name] = st

            if st == self.LOCKING:
                trg = u.get("locking_unit")
                new_targets[name] = trg
                if trg in tracks and tracks[trg].has_position:
                    tpos = tracks[trg].predicted_position(obs.now)
                    if tpos is not None and pos is not None:
                        actions.append(self._move(name, pos, tpos))
                continue

            if st == self.FROZEN:
                new_targets[name] = self.targets.get(name)
                continue

            cur = self.targets.get(name)
            if cur is not None:
                t = tracks.get(cur)
                if t is None or not t.has_position or cur in _KILLED:
                    events.append(("RELEASE", f"{name}->{cur}(目标失效)"))
                    cur = None

            # 机会锁定: 锁距内存在可锁定的敌舰 → 立即锁定最近、攻击者最少的那个
            opp = self._opportunistic_lock(name, pos, tracks, legal, obs)
            if opp is not None:
                if opp != self.targets.get(name):
                    events.append(("ASSIGN", f"{name}->{opp}(机会锁定)"))
                new_targets[name] = opp
                actions.append((f"{name} 锁定 {opp}", "lock"))
                continue

            if cur is None:
                for trk, usvs in alloc_result.items():
                    if name in usvs:
                        cur = trk
                        events.append(("ASSIGN", f"{name}->{trk}"))
                        break
            new_targets[name] = cur

            if cur is None:
                # AVAILABLE: 东向宽前沿（含 reserve 船，继续向东巡逻，可机会锁定自卫）
                actions.append(self._move(name, pos, (pos[0] + 100_000, pos[1]) if pos else None))
                continue

            t = tracks.get(cur)
            if t is None or not t.has_position:
                new_targets[name] = None
                actions.append(self._move(name, pos, (pos[0] + 100_000, pos[1]) if pos else None))
                continue
            tpos = t.predicted_position(obs.now)
            if pos is None or tpos is None:
                continue
            dist = math.hypot(tpos[0] - pos[0], tpos[1] - pos[1])

            if dist < LOCK_RANGE and legal.can_lock(name, cur):
                actions.append((f"{name} 锁定 {cur}", "lock"))
            else:
                actions.append(self._move(name, pos, tpos))

        self.targets = new_targets
        return actions

    def _opportunistic_lock(self, name, pos, tracks, legal, obs):
        if pos is None:
            return None
        best, best_key = None, None
        for tname, t in tracks.items():
            if tname in _KILLED or not t.has_position:
                continue
            if not ThreatAllocator._is_ship(tname):
                continue
            tpos = t.predicted_position(obs.now)
            if tpos is None:
                continue
            d = math.hypot(tpos[0] - pos[0], tpos[1] - pos[1])
            if d >= LOCK_RANGE:
                continue
            if not legal.can_lock(name, tname):
                continue
            key = (len(t.assigned_usvs), d)
            if best_key is None or key < best_key:
                best, best_key = tname, key
        return best

    def _move(self, name, pos, target_pos):
        if pos is None or target_pos is None:
            return (f"{name} 移动 target_speed={USV_SPEED:.1f} target_course=90.0", "move")
        crs = bearing_to(pos, target_pos)
        return (f"{name} 移动 target_speed={USV_SPEED:.1f} target_course={crs:.1f}", "move")


# ════════════════════════════════════════════════════════════════
# UAVManager —— UAV 状态机 + 电量安全（V1 逻辑 + intent 参数化）
# ════════════════════════════════════════════════════════════════
class UAVManager:
    """UAV 状态: ON_SHIP / SEARCH / REACQUIRE / RETURN / LANDING / CHARGING

    电量安全(核心，Commander 不可覆盖):
      estimated_return_time = 到最近空机库存活USV距离 / 可执行速度
      若 battery_remaining < estimated_return_time + SAFETY_MARGIN → 立即返航

    intent 可调整（不碰电量/RTB/降落安全）:
      - uav_mode / uav_priority_tracks  重搜优先级（focused_reacquire 优先指定 track）
      - recon_aggressiveness            再起飞/搜索投入的积极程度
    """

    ON_SHIP, SEARCH, REACQUIRE, RETURN, LANDING, CHARGING = \
        "ON_SHIP", "SEARCH", "REACQUIRE", "RETURN", "LANDING", "CHARGING"

    def __init__(self, enabled=True):
        self.enabled = enabled
        self.state = {}
        self.reacquire_lock = {}   # track_name -> uav_name
        self.search_dir = {}       # uav_name -> +1(向东) / -1(向西)

    def step(self, obs, tracker, legal, events, intent=None, threat_fn=None):
        if not self.enabled:
            return []
        tracks = tracker.tracks
        actions = []
        usv_info = []
        for u in obs.usvs:
            if not u.get("is_alive"):
                continue
            p = u.get("position")
            usv_info.append({
                "name": u["name"],
                "pos": (p[0], p[1]) if p else None,
                "dock": set(u.get("uav", []) or []),
            })
        docked_names = set()
        for ui in usv_info:
            docked_names |= ui["dock"]

        lost = tracker.lost_high_threat(obs.now)
        # 按 Commander 意图排序重搜优先级：优先 uav_priority_tracks，其次高威胁
        if intent and intent.uav_mode == "focused_reacquire" and intent.uav_priority_tracks:
            lost = sorted(lost, key=lambda t: (0 if t.name in intent.uav_priority_tracks else 1,
                                               -(threat_fn(t, obs.now) if threat_fn else t.confidence)))
        elif threat_fn:
            lost = sorted(lost, key=lambda t: -threat_fn(t, obs.now))

        for trk in lost:
            if trk.name in self.reacquire_lock:
                uavn = self.reacquire_lock[trk.name]
                if not any(uv.get("name") == uavn and uv.get("is_alive") and not uv.get("is_at_usv") for uv in obs.uavs):
                    del self.reacquire_lock[trk.name]

        recon = intent.recon_aggressiveness if intent else 0.6
        n_uavs = max(1, obs.uav_alive)   # 规模无关：搜索扇面随可用 UAV 数量自适应

        for u in obs.uavs:
            if not u.get("is_alive"):
                self.state[u["name"]] = None
                continue
            name = u["name"]
            batt = u.get("battery", UAV_BATTERY_TOTAL)
            at_usv = u.get("is_at_usv", True)
            pos = (u["position"][0], u["position"][1]) if u.get("position") else None
            st = self.state.get(name)

            recovery = None
            recv_d = float("inf")
            if pos is not None:
                for ui in usv_info:
                    has_other = any(d != name for d in ui["dock"])
                    if has_other:
                        continue
                    d = math.hypot(ui["pos"][0] - pos[0], ui["pos"][1] - pos[1]) if ui["pos"] else float("inf")
                    if d < recv_d:
                        recv_d, recovery = d, ui["name"]

            if at_usv:
                if st in (None, self.ON_SHIP, self.CHARGING):
                    self.state[name] = self.CHARGING
                need_search = len(lost) > 0 or obs.enemy_visible == 0 or recon >= 0.8
                if batt >= UAV_BATTERY_TOTAL * UAV_RECHARGE_THRESHOLD and need_search:
                    home = u.get("home_name")
                    if legal.can_launch(name, home):
                        actions.append(self._launch(name, home))
                        events.append(("UAV RELAUNCH", name))
                        self.state[name] = self.SEARCH
                continue

            if pos is None:
                continue
            est_ret = recv_d / UAV_FLY_SPEED if recovery else float("inf")
            # 电量安全（不允许 Commander 覆盖）
            if batt < est_ret + UAV_SAFETY_MARGIN:
                if st != self.RETURN:
                    events.append(("UAV RTB", f"{name}(电量{batt:.0f}<{est_ret:.0f}+{UAV_SAFETY_MARGIN:.0f})"))
                self.state[name] = self.RETURN

            st = self.state.get(name, self.SEARCH)

            if st in (self.SEARCH, self.REACQUIRE):
                target_track = None
                for trk in lost:
                    if trk.name in self.reacquire_lock and self.reacquire_lock[trk.name] != name:
                        continue
                    target_track = trk
                    self.reacquire_lock[trk.name] = name
                    break
                if target_track is not None:
                    self.state[name] = self.REACQUIRE
                    tpos = target_track.predicted_position(obs.now)
                    if tpos is not None and legal.can_fly(name):
                        actions.append(self._fly(name, pos, tpos))
                else:
                    self.state[name] = self.SEARCH
                    if legal.can_fly(name):
                        actions.append(self._search_fly(name, pos, n_uavs))

            if self.state.get(name) == self.RETURN:
                if recovery is None:
                    continue
                rpos = None
                for ui in usv_info:
                    if ui["name"] == recovery:
                        rpos = ui["pos"]
                        break
                if rpos is None:
                    continue
                dist = math.hypot(rpos[0] - pos[0], rpos[1] - pos[1])
                if dist <= UAV_RTB_RANGE_KM and legal.can_land(name, recovery):
                    actions.append((f"{name} 降落到 {recovery}", "land_uav"))
                    self.state[name] = self.LANDING
                    events.append(("UAV LAND", f"{name}->{recovery}"))
                elif legal.can_fly(name):
                    actions.append(self._fly(name, pos, rpos))

        return actions

    def _launch(self, name, home):
        return (f"{name} 从 {home} 起飞 target_speed={UAV_FLY_SPEED:.1f} target_course=90.0", "launch_uav")

    def _fly(self, name, pos, target_pos):
        if pos is None or target_pos is None:
            crs = 90.0
        else:
            crs = bearing_to(pos, target_pos)
        return (f"{name} 飞行 target_speed={UAV_FLY_SPEED:.1f} target_course={crs:.1f}", "fly")

    def _search_fly(self, name, pos, n_uavs):
        d = self.search_dir.get(name, 1)
        if pos is not None:
            if pos[0] >= SEARCH_X_MAX:
                d = -1
            elif pos[0] <= SEARCH_X_MIN:
                d = 1
        self.search_dir[name] = d
        idx = int(name.replace("white_uav", "")) if "white_uav" in name else 0
        # 扇面总宽 ~90°（±45°），围绕当前可用 UAV 数量的中线对称分布；
        # 不假设固定 UAV 数量（5/7/10/15 均自适应）。
        n = max(1, n_uavs)
        center = (n + 1) / 2.0
        step_deg = 90.0 / n
        if d > 0:
            crs = 90.0 + (idx - center) * step_deg
        else:
            crs = 270.0 + (idx - center) * step_deg
        crs = crs % 360.0
        return (f"{name} 飞行 target_speed={UAV_FLY_SPEED:.1f} target_course={crs:.1f}", "fly")


# ════════════════════════════════════════════════════════════════
# ActionSafety —— 动作安全过滤（与 V1 相同）
# ════════════════════════════════════════════════════════════════
class ActionSafety:
    """对候选动作双重校验(legal_actions + 实时状态), 杜绝 400 批量失败。"""

    def __init__(self):
        pass

    def filter(self, actions, obs, legal):
        usv_state = {u["name"]: u for u in obs.usvs}
        uav_state = {u["name"]: u for u in obs.uavs}
        seen_unit = set()
        out = []
        for text, atype in actions:
            unit = self._unit_of(text)
            if unit is None:
                continue
            if unit in seen_unit:
                continue
            if atype in ("move", "lock"):
                u = usv_state.get(unit)
                if u is None or not u.get("is_alive"):
                    continue
                if u.get("is_frozen"):
                    continue
                if atype == "move" and not legal.can_move(unit):
                    continue
                if atype == "lock":
                    if u.get("is_locking"):
                        continue
                    target = self._target_of(text)
                    if target is None or not legal.can_lock(unit, target):
                        continue
            elif atype in ("launch_uav", "fly", "land_uav"):
                ua = uav_state.get(unit)
                if ua is None or not ua.get("is_alive"):
                    continue
                if atype == "launch_uav":
                    if not ua.get("is_at_usv"):
                        continue
                    home = self._home_of(text)
                    if home is None or not legal.can_launch(unit, home):
                        continue
                elif atype == "fly":
                    if ua.get("is_at_usv"):
                        continue
                    if not legal.can_fly(unit):
                        continue
                elif atype == "land_uav":
                    if ua.get("is_at_usv"):
                        continue
                    usv = self._target_of(text)
                    if usv is None or not legal.can_land(unit, usv):
                        continue
            elif atype == "noop":
                pass
            else:
                continue
            seen_unit.add(unit)
            out.append({"action_text": text, "action_type": atype})
        return out

    @staticmethod
    def _unit_of(text):
        parts = text.split()
        return parts[0] if parts else None

    @staticmethod
    def _target_of(text):
        parts = text.split()
        return parts[2] if len(parts) >= 3 else None

    @staticmethod
    def _home_of(text):
        parts = text.split()
        return parts[2] if len(parts) >= 3 else None


# ════════════════════════════════════════════════════════════════
# AgentMain —— 主循环（V1 + Commander 集成）
# ════════════════════════════════════════════════════════════════
class AgentMain:
    def __init__(self, use_uavs=True, max_steps=40000):
        self.client = ApiClient()
        self.tracker = TrackManager()
        self.allocator = ThreatAllocator()
        self.usv_ctrl = USVController()
        self.uav_mgr = UAVManager(enabled=use_uavs)
        self.safety = ActionSafety()
        self.use_uavs = use_uavs
        self.max_steps = max_steps
        self.prev_black_killed = 0
        self.step = 0

        # ---- LLM Commander layer ----
        self.llm_enabled = (os.getenv("LLM_ENABLED", "true").strip().lower() == "true")
        self.skill_loader = SkillLoader()
        skill_text = self.skill_loader.load()
        self.summarizer = TacticalSummarizer(self.allocator)
        self.commander = LLMCommander(enabled=self.llm_enabled, skill_text=skill_text)
        self.intent = self.commander.get_intent()

        # ---- 统计与触发器状态 ----
        self.stats = {"first_detection": None, "first_lock": None,
                      "victory_time": None, "result": None}
        self._ever_saw_enemy = False
        self._prev_visible = None
        self._prev_usv_alive = None
        self._logged_intent_desc = None

    # ── 事件聚合 ──
    def _emit_events(self, evs):
        for tag, detail in evs:
            print(f"      [{tag}] {detail}")

    # ── Commander 触发检测 ──
    def _detect_trigger(self, obs):
        for t in self.tracker.tracks.values():
            if not t.has_position:
                continue
            pos = t.predicted_position(obs.now)
            if pos is not None and pos[0] < 90_000.0:
                return "breakthrough_risk"
        usv_st = self.usv_ctrl.state
        n_frz = sum(1 for s in usv_st.values() if s == USVController.FROZEN)
        if n_frz >= 3:
            return "multi_frozen"
        if self._prev_usv_alive is not None and obs.usv_alive < self._prev_usv_alive:
            return "friendly_loss"
        if self.tracker.lost_high_threat(obs.now):
            return "lost_high_threat"
        if self._prev_visible is not None and obs.enemy_visible - self._prev_visible >= 3:
            return "threat_spike"
        if not self._ever_saw_enemy and obs.enemy_visible > 0:
            return "first_detect"
        return "periodic"

    def _record_stats(self, obs, events):
        if self.stats["first_detection"] is None:
            if any(e[0] == "DETECT" for e in events) or obs.enemy_visible > 0:
                self.stats["first_detection"] = obs.now
        if self.stats["first_lock"] is None and any(u.get("is_locking") for u in obs.usvs):
            self.stats["first_lock"] = obs.now
        if obs.ended and self.stats["victory_time"] is None:
            self.stats["victory_time"] = obs.now
            self.stats["result"] = obs.result

    # ── 单步 ──
    def step_once(self):
        st = self.client.status()
        if not isinstance(st, dict):
            return False
        now = parse_sim_time(st.get("局内时间", "00:00:00"))
        obs = Obs(st, now)
        legal_raw = self.client.legal_actions()
        legal = LegalSet(legal_raw) if isinstance(legal_raw, dict) else LegalSet({})

        # 航迹 + 事件
        events = self.tracker.update(obs)
        self.tracker.reconcile_assigned(obs, self.usv_ctrl.targets)
        kill_evs, killed = self.tracker.kill_detect(obs, self.prev_black_killed)
        events += kill_evs
        _KILLED.update(killed)
        self.prev_black_killed = obs.black_killed

        # 威胁分配（意图参数化：focus / emergency / reserve / priority / bias）
        self.intent = self.commander.get_intent()
        alloc = self.allocator.allocate_usvs(
            {n: t for n, t in self.tracker.tracks.items()}, obs.usvs,
            self.usv_ctrl.targets, now, intent=self.intent)

        # USV / UAV 动作
        usv_acts = self.usv_ctrl.step(obs, self.tracker.tracks, legal, alloc, events)
        uav_acts = self.uav_mgr.step(obs, self.tracker, legal, events,
                                     intent=self.intent,
                                     threat_fn=lambda t, n: self.allocator.threat_score(t, n))
        self._emit_events(events)

        # 统计 + Commander 后台请求（快照摘要，绝不等待 LLM）
        self._record_stats(obs, events)
        summary_text, valid_tracks = self.summarizer.build(
            obs, self.tracker, self.usv_ctrl, self.uav_mgr, self.intent)
        trigger = self._detect_trigger(obs)
        self.commander.maybe_request(obs.now, summary_text, valid_tracks, trigger)
        self._prev_visible = obs.enemy_visible
        self._prev_usv_alive = obs.usv_alive
        self._ever_saw_enemy = self._ever_saw_enemy or obs.enemy_visible > 0

        # 安全过滤
        safe = self.safety.filter(usv_acts + uav_acts, obs, legal)
        if not safe:
            safe = [{"action_text": "空操作，等待一个宏观步 [noop]", "action_type": "noop"}]

        resp = self.client.apply(safe)

        self._maybe_log(obs, alloc, safe, resp)
        return not obs.ended

    def _maybe_log(self, obs, alloc, safe, resp):
        if self.step % LOG_INTERVAL != 0 and not self.step == 0:
            return
        st = self.usv_ctrl.state
        n_avail = sum(1 for s in st.values() if s == USVController.AVAILABLE)
        n_inter = sum(1 for s in st.values() if s == USVController.INTERCEPTING)
        n_lock = sum(1 for s in st.values() if s == USVController.LOCKING)
        n_frz = sum(1 for s in st.values() if s == USVController.FROZEN)
        n_dead = sum(1 for s in st.values() if s == USVController.DEAD)
        uav_st = self.uav_mgr.state
        n_air = sum(1 for v in uav_st.values() if v in (UAVManager.SEARCH, UAVManager.REACQUIRE))
        n_rtb = sum(1 for v in uav_st.values() if v == UAVManager.RETURN)
        n_chg = sum(1 for v in uav_st.values() if v in (UAVManager.CHARGING, UAVManager.LANDING))
        tracks = self.tracker.tracks
        n_vis = sum(1 for t in tracks.values() if t.is_visible(obs.now))
        n_lost = len(tracks) - n_vis
        n_eng = sum(1 for t in tracks.values() if t.engaged)
        top = sorted(tracks.values(), key=lambda t: -self.allocator.threat_score(t, obs.now))[:3]
        top_s = " ".join(t.name + (f"(x{int(t.predicted_position(obs.now)[0]):,})"
                                   if t.has_position and t.predicted_position(obs.now) else "")
                         for t in top)
        print(f"[t={obs.now:,.0f}s] step={self.step} | USV: {obs.usv_alive}/{obs.usv_total} "
              f"(avail={n_avail} int={n_inter} lock={n_lock} frz={n_frz}) | "
              f"UAV: air={n_air} rtb={n_rtb} chg={n_chg} | "
              f"TRACKS: vis={n_vis} lost={n_lost} engaged={n_eng} | TOP: {top_s} | "
              f"KILL={obs.black_killed} | ACTIONS={len(safe)} | "
              f"INTENT: focus={self.intent.focus_level} ratio={self.intent.reserve_ratio:.2f}")

        # Commander 意图应用日志（变化时打印一次）
        desc = self.intent.describe()
        if desc != self._logged_intent_desc:
            self._logged_intent_desc = desc
            print("  [INTENT APPLIED]")
            print(f"    ThreatAllocator: focus {self.intent.focus_level} "
                  f"emergency {self.intent.emergency_focus_level} "
                  f"reserve_ratio {self.intent.reserve_ratio:.2f} "
                  f"reserve_usvs {self.intent.reserve_usvs} bias {self.intent.threat_bias}")
            print(f"    UAVManager: mode {self.intent.uav_mode} "
                  f"uav_priority {self.intent.uav_priority_tracks}")

    def run(self):
        print("=" * 72)
        print("HYBRID AGENT V2 — LLM Commander + Deterministic Core")
        print(f"  启用UAV: {self.use_uavs} | LLM_ENABLED: {self.llm_enabled}")
        print("=" * 72)
        r = self.client.start()
        if not r or not r.get("成功"):
            print("启动失败(确认服务在运行)"); return
        print(f"对局 {r.get('对局编号')} 开始")
        self.prev_black_killed = 0

        while self.step < self.max_steps:
            self.step += 1
            if not self.step_once():
                break
            time.sleep(0.05)

        # 结果
        print("\n" + "=" * 72)
        res = self.client.result()
        if isinstance(res, dict):
            print(f"对局结果: {res.get('对局结果')} — {res.get('结果说明')}")
            sc = res.get("奖励信号", {})
            print(f"  击杀蓝舰: {sc.get('black_killed')} | 命中: {sc.get('black_hit')} | "
                  f"我方USV损失: {sc.get('white_ship_killed')} | UAV损失: {sc.get('white_uav_killed')} | "
                  f"突破: {sc.get('black_breakthrough')}")
            # 权威结果以 /result 为准：引擎在 agent 最后一步 /status 里可能因
            # 击杀计数滞后（black_ship_alive 尚未翻 0）而临时报 Defeat(突破)，
            # 但 /result 取全新状态判定 → 全歼优先于突破，结果一致可靠。
            self._print_meta(sc, final_result=res.get('对局结果'))
        self.client.stop()
        print("Done")

    def _print_meta(self, sc, final_result=None):
        cs = self.commander.stats
        n = cs["calls"]
        avg = (cs["latency_sum"] / n) if n else 0.0
        result = final_result or self.stats["result"]
        print(f"[META] result={result} "
              f"victory_time={self.stats['victory_time']} "
              f"first_detection={self.stats['first_detection']} "
              f"first_lock={self.stats['first_lock']} "
              f"enemy_kills={sc.get('black_killed', 0)} "
              f"friendly_usv_losses={sc.get('white_ship_killed', 0)} "
              f"llm_calls={cs['calls']} llm_parse_failures={cs['parse_failures']} "
              f"llm_api_failures={cs['api_failures']} llm_avg_latency={avg:.1f}")


# ════════════════════════════════════════════════════════════════
# TrackManager 单测（离线 mock，与 V1 相同）
# ════════════════════════════════════════════════════════════════
def selftest_trackmanager():
    print("=== TrackManager 单测 ===")
    class FakeObs:
        def __init__(self, now, active=(), passive=()):
            self.now = now
            self.active = [{"name": n, "position": p, "velocity": v} for n, p, v in active]
            self.passive = [{"name": n, "bearing": b} for n, b in passive]
            self.usvs = []
            self.black_killed = 0

    tm = TrackManager()
    ev = tm.update(FakeObs(0.0, [("b1", (250000, 300000), (-10, 0))]))
    assert any(e[0] == "DETECT" and e[1] == "b1" for e in ev), "未检测到新目标"
    t = tm.tracks["b1"]
    assert t.has_position and t.last_velocity == (-10, 0) and t.is_visible(0.0)
    print("  [1] 检测 ✓")

    ev = tm.update(FakeObs(60.0, []))
    pp = tm.tracks["b1"].predicted_position(60.0)
    assert pp == (249400, 300000), f"预测错误 {pp}"
    assert tm.tracks["b1"].confidence == 0.5, "60s应降为估计置信"
    print("  [2] 常量速度外推 + 置信衰减 ✓")

    tm.update(FakeObs(65.0, [("b1", (249350, 300000), (-10, 0))]))
    assert tm.tracks["b1"].confidence == 1.0 and tm.tracks["b1"].is_visible(65.0)
    print("  [3] 重新探测恢复 ✓")

    tm.update(FakeObs(255.0, []))
    assert "b1" not in tm.tracks, "190s后应丢弃"
    print("  [4] 过期丢弃 ✓")

    tm2 = TrackManager()
    tm2.update(FakeObs(0.0, [], [("b2", 120.0)]))
    assert "b2" in tm2.tracks and not tm2.tracks["b2"].has_position
    assert tm2.tracks["b2"].bearing == 120.0
    print("  [5] 被动告警 ✓")

    tm3 = TrackManager()
    tm3.update(FakeObs(0.0, [("b3", (240000, 300000), (-10, 0))]))
    tm3.tracks["b3"].engaged = True
    tm3.tracks["b3"].assigned_usvs = {"white_usv1", "white_usv2"}
    evs, killed = tm3.kill_detect(FakeObs(100.0), prev_black_killed=0)
    assert killed == [], "应无击沉(black_killed未增加)"
    evs, killed = tm3.kill_detect(FakeObs(100.0, active=[]), prev_black_killed=0)
    assert killed == []
    fo = FakeObs(100.0, active=[])
    fo.black_killed = 1
    evs, killed = tm3.kill_detect(fo, prev_black_killed=0)
    assert killed == ["b3"], f"应判定击沉b3, got {killed}"
    assert "b3" in tm3.killed_names and "b3" not in tm3.tracks
    print("  [6] 击沉判定 ✓")

    tm4 = TrackManager()
    tm4.update(FakeObs(0.0, [("b4", (200000, 300000), (-10, 0))]))
    tm4.tracks["b4"].engaged = True
    tm4.tracks["b4"].assigned_usvs = {"white_usv1"}
    for t in (100.0, 200.0, 400.0, 620.0):
        tm4.update(FakeObs(t, [("b4", (200000, 300000), (-10, 0))]))
        tm4.tracks["b4"].engaged = True
    evs, killed = tm4.kill_detect(FakeObs(650.0, active=[("b4", (200000, 300000), (-10, 0))]), prev_black_killed=1)
    assert killed == ["b4"], f"静止>600s应判定尸体击沉, got {killed}"
    assert "b4" not in tm4.tracks and "b4" in tm4.killed_names
    print("  [7] 尸体检测(静止>600s) ✓")

    print("=== TrackManager 全部通过 ===")
    return True


# ════════════════════════════════════════════════════════════════
# Commander 层单测（离线 mock，不需要服务器）
# ════════════════════════════════════════════════════════════════
def mocktest_commander():
    print("=== Commander Layer 离线单测 ===")
    ok = True

    def check(cond, msg):
        nonlocal ok
        print(f"  [{'PASS' if cond else 'FAIL'}] {msg}")
        if not cond:
            ok = False

    # 1) SkillLoader 正常读取 + fallback 不崩溃
    loader = SkillLoader()
    text = loader.load()
    check(text and "Maritime Commander Skill" in text, "SkillLoader 正常读取 SKILL.md")
    bad = SkillLoader("/nonexistent_dir/SKILL.md").load()
    check(bool(bad) and "fallback" in bad.lower(), "SkillLoader 路径失败 fallback 不崩溃")

    # 2) TacticalSummarizer 不含 black runtime truth / 硬编码先验
    class FakeObs:
        def __init__(self, now, active):
            self.now = now
            self.active = [{"name": n, "position": p, "velocity": v} for n, p, v in active]
            self.passive = []
            self.usvs = []
            self.uavs = []
            self.usv_alive = 15
            self.usv_total = 15
            self.uav_alive = 15
            self.uav_total = 15
            self.uav_flying = 0
            self.enemy_visible = 1
            self.black_killed = 0
            self.black_hit = 0
            self.white_ship_killed = 0
            self.white_uav_killed = 0
            self.black_breakthrough = 0

    tracker = TrackManager()
    fo = FakeObs(0.0, [("E3", (150000, 300000), (-12, 2))])
    tracker.update(fo)
    summ = TacticalSummarizer(ThreatAllocator())
    s_text, tids = summ.build(fo, tracker, USVController(), UAVManager(enabled=True),
                              DEFAULT_INTENT)
    forbidden = ["black_usv_states", "black_uav_states", "black_strategy", "locked_times",
                 "vx=-10", "260000", "BLACK_Y"]
    check(all(b not in s_text for b in forbidden),
          "摘要不含 black runtime truth / 硬编码先验")
    check("E3" in s_text and tids == ["E3"], "摘要包含观测到的航迹")

    # 3) JSON 正常 parse
    good = ('{"posture":"aggressive","focus_level":3,"emergency_focus_level":4,'
            '"reserve_usvs":2,"threat_bias":"nearest","priority_tracks":["E3"],'
            '"uav_mode":"focused_reacquire","uav_priority_tracks":["E3"],'
            '"recon_aggressiveness":0.9,"engagement_aggressiveness":0.8,"reason":"t"}')
    intent, err = CommanderIntentAdapter.parse(good, ["E3", "E7"])
    check(intent is not None and intent.posture == "aggressive" and intent.focus_level == 3,
          "JSON 正常 parse")
    check(err is None, "parse 无错误")

    # 4) malformed / markdown 前缀 fallback
    intent, err = CommanderIntentAdapter.parse("I think we should move east", ["E3"])
    check(intent is None and err == "malformed_json", "非 JSON 文本 → fallback")
    intent, err = CommanderIntentAdapter.parse("```json\n{\"focus_level\":\"broken\"\n```", ["E3"])
    check(intent is None, "markdown 围栏 + 损坏 JSON → fallback")

    # 5) 数值 clamp
    intent, _ = CommanderIntentAdapter.parse(
        '{"focus_level":10,"emergency_focus_level":9,"reserve_usvs":99,'
        '"recon_aggressiveness":5,"engagement_aggressiveness":-3}', [])
    check(intent.focus_level == 3 and intent.emergency_focus_level == 4
          and intent.reserve_usvs == 8 and intent.recon_aggressiveness == 1.0
          and intent.engagement_aggressiveness == 0.0,
          "数值 clamp (focus=3 emergency=4 reserve=8 recon=1.0 engage=0.0)")

    # 6) 无效 track id 删除
    intent, _ = CommanderIntentAdapter.parse(
        '{"priority_tracks":["E3","GHOST","E7",""],"uav_priority_tracks":["GHOST"]}',
        ["E3", "E7"])
    check(intent.priority_tracks == ["E3", "E7"] and intent.uav_priority_tracks == [],
          "无效 track id 被删除, 空串被忽略")

    # 7) LLM 慢调用不阻塞主循环 + in_flight 保护 + 原子更新 + cooldown
    def slow_call(system, user):
        time.sleep(1.2)
        return '{"posture":"cautious","focus_level":1,"reason":"slow"}'

    cmdr = LLMCommander(enabled=True, skill_text=text, call_fn=slow_call)
    t0 = time.time()
    started = cmdr.maybe_request(100.0, "summary", ["E3"], "first_detect")
    dt = time.time() - t0
    check(started and dt < 0.2, f"maybe_request 不阻塞 (returned in {dt:.2f}s)")
    check(cmdr.in_flight, "in_flight 置位")
    t0 = time.time()
    started2 = cmdr.maybe_request(100.0, "summary", ["E3"], "periodic")
    check(not started2 and time.time() - t0 < 0.2, "in_flight 时第二个请求不启动")
    time.sleep(1.8)
    check(cmdr.get_intent().posture == "cautious" and not cmdr.in_flight,
          "后台完成后 latest_intent 原子更新")
    check(cmdr.stats["calls"] == 1, "LLM 调用计数=1")
    check(not cmdr.maybe_request(650.0, "s", ["E3"], "periodic"), "cooldown 内不重复请求")
    check(cmdr.maybe_request(1800.0, "s", ["E3"], "periodic"), "超过 cooldown 后恢复请求")

    # 8) LLM_ENABLED=false 完全退化
    cmdr2 = LLMCommander(enabled=False, skill_text=text)
    check(not cmdr2.maybe_request(0.0, "s", [], "periodic"), "LLM disabled 时不发起请求")
    check(cmdr2.get_intent() == DEFAULT_INTENT, "LLM disabled 时保持 DEFAULT_INTENT")

    print("=== Commander Layer 全部通过 ===" if ok else "=== Commander Layer 存在 FAIL ===")
    return ok


# ════════════════════════════════════════════════════════════════
# Scale Generalization 单测（离线 mock，不需要服务器）
# ════════════════════════════════════════════════════════════════
def scaletest_generalization():
    """验证"规模是上下文而非策略"：同一 agent 在 5/8/10/15 不同兵力下无规模耦合。"""
    print("=== Scale Generalization 离线单测 ===")
    ok = True

    def check(cond, msg):
        nonlocal ok
        print(f"  [{'PASS' if cond else 'FAIL'}] {msg}")
        if not cond:
            ok = False

    # 1) reserve_ratio 解析与 clamp (0~0.5)
    intent, _ = CommanderIntentAdapter.parse('{"reserve_ratio":0.9}', [])
    check(intent.reserve_ratio == 0.5, f"reserve_ratio 0.9 → clamp 0.5 (got {intent.reserve_ratio})")
    intent, _ = CommanderIntentAdapter.parse('{"reserve_ratio":-0.3}', [])
    check(intent.reserve_ratio == 0.0, f"reserve_ratio -0.3 → clamp 0.0 (got {intent.reserve_ratio})")
    intent, _ = CommanderIntentAdapter.parse('{}', [])
    check(intent.reserve_ratio == 0.20 and intent.reserve_usvs is None,
          "默认 reserve_ratio=0.20, reserve_usvs=None（用比例）")

    # 2) 旧字段 reserve_usvs 向后兼容
    intent, _ = CommanderIntentAdapter.parse('{"reserve_usvs":2}', [])
    check(intent.reserve_usvs == 2, "旧字段 reserve_usvs=2 仍解析（显式覆盖比例）")

    # 3) ThreatAllocator 比例预备：reserve = round(可用×ratio)，各规模自适应
    alloc = ThreatAllocator()

    def make_track(name, x):
        t = EnemyTrack(name, 0.0)
        t.last_position = (x, 300000.0)
        t.last_velocity = (-10.0, 0.0)
        t.has_position = True
        t.confidence = 1.0
        return t

    for n, exp in ((5, 1), (8, 2), (10, 2), (15, 3)):
        # 敌舰名含 "usv"（真实对局为 black_usv1..N），_is_ship 依赖该命名
        tracks = {f"black_usv{i}": make_track(f"black_usv{i}", 180000.0)
                  for i in range(1, 3)}
        usvs = [{"name": f"white_usv{i}", "is_alive": True,
                 "position": [0.0, 300000.0 + i]} for i in range(1, n + 1)]
        usv_map = {f"white_usv{i}": None for i in range(1, n + 1)}
        res = alloc.allocate_usvs(tracks, usvs, usv_map, 0.0,
                                  intent=StrategicIntent(reserve_ratio=0.20))
        spent = sum(len(v) for v in res.values())
        check(0 < spent <= n - exp,
              f"{n} USV / 预备 {exp} → 实际分配≤{n - exp} (spent={spent})")

    # 4) 5v5 边界：仅 1 艘可用但 focus=2 → 不报错且动态降级为 1 艘
    tracks = {f"black_usv{i}": make_track(f"black_usv{i}", 180000.0)
              for i in range(1, 4)}
    usvs = [{"name": "white_usv1", "is_alive": True, "position": [0.0, 300000.0]}]
    res = alloc.allocate_usvs(tracks, usvs, {"white_usv1": None}, 0.0,
                              intent=StrategicIntent(focus_level=2,
                                                     emergency_focus_level=3,
                                                     reserve_ratio=0.20))
    check(sum(len(v) for v in res.values()) == 1, "仅 1 艘可用时只分配 1 艘（无错误）")

    # 5) TacticalSummarizer top-K：15 条航迹时只 detail K=8 条，其余聚合
    tracker = TrackManager()
    for i in range(1, 16):
        tracker.tracks[f"E{i}"] = make_track(f"E{i}", 200000.0 - i * 2000)

    class MiniObs:
        now = 0.0
        usv_alive = 15
        uav_alive = 15
        enemy_visible = 15
        usvs = []
        uavs = []

    summ = TacticalSummarizer(alloc)
    s_text, tids = summ.build(MiniObs(), tracker, USVController(),
                              UAVManager(enabled=True), StrategicIntent())
    check("count=15" in s_text and "visible=15" in s_text, "摘要含聚合 count/visible")
    check("more tracks not detailed" in s_text, "超出 K 的航迹以聚合概括")
    n_detail = s_text.count("  engaged=")   # 每条 detail 一条
    check(n_detail == 8, f"detail 块数 = K = 8 (got {n_detail})")
    check(len(tids) == 15, "valid_tracks 仍返回全部 15 条")
    check("SCENARIO" not in s_text and "10v10" not in s_text and "30v30" not in s_text,
          "摘要不含规模/场景标签（Commander 场景标签盲）")

    # 6) UAV 搜索扇面随数量自适应、围绕东向对称，且不假设固定数量
    import re
    mgr = UAVManager(enabled=True)

    def crs_of(s):
        return float(re.search(r"target_course=([\d.]+)", s).group(1))

    vals5 = sorted(crs_of(mgr._search_fly(f"white_uav{i}", (200000, 300000), 5)[0])
                   for i in range(1, 6))
    check(len(vals5) == 5 and abs(vals5[0] - 90) == abs(vals5[-1] - 90),
          f"5 UAV 扇面以 90° 对称 (vals={[round(v) for v in vals5]})")
    vals15 = sorted(crs_of(mgr._search_fly(f"white_uav{i}", (200000, 300000), 15)[0])
                    for i in range(1, 16))
    check(len(vals15) == 15 and abs(vals15[0] - 90) == abs(vals15[-1] - 90),
          "15 UAV 扇面以 90° 对称且 15 个航向互异")

    print("=== Scale Generalization 全部通过 ===" if ok
          else "=== Scale Generalization 存在 FAIL ===")
    return ok


# ════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    use_uavs = True
    selftest = False
    mocktest = False
    scaletest = False
    for a in sys.argv[1:]:
        if a == "--no-uav":
            use_uavs = False
        if a == "--selftest":
            selftest = True
        if a == "--mocktest":
            mocktest = True
        if a == "--scaletest":
            scaletest = True
    if selftest:
        ok = selftest_trackmanager()
        sys.exit(0 if ok else 1)
    if scaletest:
        ok = scaletest_generalization()
        sys.exit(0 if ok else 1)
    if mocktest:
        ok = mocktest_commander()
        sys.exit(0 if ok else 1)
    AgentMain(use_uavs=use_uavs).run()
