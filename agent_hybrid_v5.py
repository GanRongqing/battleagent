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

import runtime_audit  # noqa: E402  per-step A→F audit persistence (opt-in, instrumentation-only)

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
DROP_AGE_SHIP = 300.0     # 敌 USV 丢弃更晚（机动目标更易"短暂消失后重现"，避免过早忘目标）
CORPSE_AGE = 600.0        # 尸体检测: 被锁定位置持续>600s不变 → 已击沉

# ── Maneuver-aware belief 参数（V3）──
MANEUVER_HEADING_DEG = 20.0   # 相邻观测航向差 > 该值记一次"转向事件"
MANEUVER_TURN_WINDOW = 4      # 近 N 次观测内统计转向事件
UNCERT_BASE = 4000.0          # 刚看到时的最小不确定半径(m)
UNCERT_GROWTH = 45.0          # 每丢失 1s 不确定半径增长(m)
MANEUVER_UNCERT = 12000.0     # maneuver_score 贡献的额外不确定半径(m)
POINT_CONF_MANEUVER_PENALTY = 0.4   # maneuver 对点预测置信的惩罚系数
POINT_CONF_ERROR_PENALTY = 0.5      # 预测一致性差对点预测置信的惩罚系数
MAX_PRED_ERROR = 5000.0       # 预测误差超过该值视为"预测不一致"
RECENT_WINDOW = 6             # recent_* 历史窗口长度

# ── Sensor-assisted / Standoff 参数（V3，Phase D）──
# 交战保持距离放在**自身 35km 雷达内**（~34km）：保证 USV 即使失去 UAV 覆盖也能
# 自探测重锁（避免 37km 盲带导致"最后 1 艘漏网"）。锁距 40km 不受影响。
LOCK_BAND_MID = 34_000.0      # 交战保持距离（目标 ~34km，位于自身雷达内）
LOCK_BAND_INNER = 29_500.0    # 过近硬下限：低于此则回拉（避免点对点白刃）
LOCK_BAND_OUTER = 36_500.0    # 高于此则收拢（防止锁断，且仍 <40km）

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

# ── V5: GLOBAL_REACQUIRE / coverage map / composition-agnostic ──
COVERAGE_CELL = 30_000.0            # coverage grid 格子大小（由战场几何固定，不随兵力规模变）
COVERAGE_X0, COVERAGE_X1 = 0.0, 300_000.0
COVERAGE_Y0, COVERAGE_Y1 = 80_000.0, 620_000.0
COVERAGE_STALE = 300.0              # 单元格超过该时长未覆盖视为"陈旧"
GLOBAL_REACQUIRE_DELAY = 90.0       # 无 ship track 持续超过该时间 → GLOBAL_REACQUIRE
SCREEN_X = 120_000.0                # GLOBAL_REACQUIRE 下 USV 防御屏列 x（突破相关区前方）
MISSION_NORMAL, MISSION_GLOBAL_REACQUIRE, MISSION_TERMINAL = "NORMAL_COMBAT", "GLOBAL_REACQUIRE", "TERMINAL"


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
# TrackManager —— Maneuver-aware Belief Tracker（V3，观测纯正）
# ════════════════════════════════════════════════════════════════
class EnemyTrack:
    """单条敌情航迹 = 观测驱动的信念（belief），不是真值。

    V3 新增（相对 V1/V2）:
      - heading / prev_heading / turn_events         转向检测
      - maneuver_score                                机动度(0~1)
      - point_confidence                              点预测置信(受机动/一致性惩罚)
      - uncertainty_radius                            不确定性半径(随时间/机动增长)
      - prediction_consistency                        预测一致性(历史误差)
      - is_ship / is_uav                              敌类型（名称观测，供分配/摘要）
      - predicted_region()                            信念区域(center, radius)
    """
    __slots__ = ("name", "last_position", "last_velocity", "last_seen_time",
                 "first_seen_time", "confidence", "has_position", "bearing",
                 "engaged", "assigned_usvs", "seen_count", "last_moved_time",
                 "prev_heading", "heading", "turn_events", "maneuver_score",
                 "point_confidence", "uncertainty_radius", "pred_errors",
                 "recent_velocities", "recent_positions", "is_ship",
                 "_w6_intercept")

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
        self.prev_heading = None
        self.heading = None
        self.turn_events = 0
        self.maneuver_score = 0.0
        self.point_confidence = 1.0
        self.uncertainty_radius = UNCERT_BASE
        self.pred_errors = []
        self.recent_velocities = []
        self.recent_positions = []
        # 敌类型：名称来自观测（雷达捕获/被动告警的 name 字段）。"usv" → 舰（突破/攻击）；
        # 否则视为 UAV（侦察/信息威胁）。仅公共命名规则，非敌方运行时真值。
        self.is_ship = ("usv" in (name or "").lower())
        # W6 optional intercept override (None = V5 behavior). Set by anti_evasion harness.
        self._w6_intercept = None

    def _heading_of(self, vel):
        import math as _m
        if vel is None or len(vel) < 2:
            return None
        vx, vy = vel[0], vel[1]
        if vx * vx + vy * vy < 1e-6:
            return None
        return _m.degrees(_m.atan2(vx, vy)) % 360.0

    def update_obs(self, pos, vel, now):
        # 预测一致性：用"上次的状态外推到 now"与"本次实测"对比
        if pos is not None and len(pos) >= 2 and self.last_position is not None \
                and self.last_velocity is not None:
            pred = self._extrapolate(self.last_position, self.last_velocity,
                                     now - self.last_seen_time)
            err = ((pred[0] - pos[0]) ** 2 + (pred[1] - pos[1]) ** 2) ** 0.5
            self.pred_errors.append(err)
            if len(self.pred_errors) > RECENT_WINDOW:
                self.pred_errors.pop(0)
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
            self.recent_positions.append((pos[0], pos[1]))
            if len(self.recent_positions) > RECENT_WINDOW:
                self.recent_positions.pop(0)
        if vel is not None and len(vel) >= 2:
            self.last_velocity = (vel[0], vel[1])
            self.recent_velocities.append((vel[0], vel[1]))
            if len(self.recent_velocities) > RECENT_WINDOW:
                self.recent_velocities.pop(0)
            h = self._heading_of(vel)
            if h is not None:
                if self.heading is not None:
                    diff = abs((h - self.heading + 180.0) % 360.0 - 180.0)
                    if diff > MANEUVER_HEADING_DEG:
                        self.turn_events += 1
                self.prev_heading = self.heading
                self.heading = h
        self.last_seen_time = now
        self.confidence = 1.0   # 重新看到即恢复高置信
        self.seen_count += 1
        # maneuver score：基于近窗口内转向事件与速度向量变化
        n = len(self.recent_velocities)
        if n >= 2:
            v0 = self.recent_velocities[-2]
            v1 = self.recent_velocities[-1]
            dv = ((v1[0] - v0[0]) ** 2 + (v1[1] - v0[1]) ** 2) ** 0.5
        else:
            dv = 0.0
        turns = min(1.0, self.turn_events / 3.0)
        vel_change = min(1.0, dv / 8.0)
        self.maneuver_score = min(1.0, max(turns, vel_change))
        self._update_point_confidence()

    def _update_point_confidence(self):
        c = 1.0
        c *= (1.0 - POINT_CONF_MANEUVER_PENALTY * self.maneuver_score)
        if self.pred_errors:
            avg_err = sum(self.pred_errors) / len(self.pred_errors)
            if avg_err > MAX_PRED_ERROR:
                c *= (1.0 - POINT_CONF_ERROR_PENALTY)
        self.point_confidence = max(0.1, c)

    @staticmethod
    def _extrapolate(pos, vel, dt):
        return (pos[0] + vel[0] * dt, pos[1] + vel[1] * dt)

    def stationary_duration(self, now):
        """位置持续不变的时间(s)。冻结上限300s, 持续>CORPSE_AGE即尸体。"""
        return now - self.last_moved_time

    def age(self, now):
        return now - self.last_seen_time

    def is_visible(self, now):
        return self.age(now) < HIGH_CONF_AGE

    def predicted_position(self, now):
        """常量速度外推（信念中心，不是真值）。

        W6 hook: if `_w6_intercept` is set (by the anti-evasion harness), the interceptor
        aims at that corridor point instead of the raw extrapolation. None -> V5 behavior.
        """
        if self._w6_intercept is not None:
            return tuple(self._w6_intercept)
        if self.last_position is None:
            return None
        if self.last_velocity is None:
            return self.last_position
        return self._extrapolate(self.last_position, self.last_velocity,
                                 now - self.last_seen_time)

    def uncertainty(self, now):
        """当前不确定半径(m)：随丢失时间与机动度增长。"""
        age = max(0.0, now - self.last_seen_time)
        return (UNCERT_BASE + UNCERT_GROWTH * age
                + MANEUVER_UNCERT * self.maneuver_score)

    def predicted_region(self, now):
        """返回 (center, radius)。center 为信念中心，radius 为不确定半径。"""
        c = self.predicted_position(now)
        if c is None:
            return None, 0.0
        return c, self.uncertainty(now)

    def __repr__(self):
        return f"EnemyTrack({self.name}, conf={self.confidence:.2f}, " \
               f"pc={self.point_confidence:.2f}, man={self.maneuver_score:.2f})"


class TrackManager:
    """维护所有已知敌舰航迹。V3: 机动感知信念跟踪。"""

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
            drop_at = DROP_AGE_SHIP if t.is_ship else DROP_AGE
            if age >= drop_at:
                to_drop.append(name)
            elif age >= HIGH_CONF_AGE:
                t.confidence = 0.5
            else:
                t.confidence = 1.0
            # 丢失时不确定半径持续增长（在读取端实时计算，这里只做年龄维护）
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

    def reacquire_candidates(self, now, max_age=EST_CONF_AGE):
        """高威胁丢失航迹，用于 UAV region reacquire（含不确定半径）。"""
        out = []
        for t in self.tracks.values():
            if not t.is_ship:
                continue  # 只重搜敌舰（敌 UAV 不构成突破威胁）
            if not t.has_position or t.is_visible(now):
                continue
            age = t.age(now)
            if age >= max_age:
                continue
            if t.confidence >= 0.5:
                out.append(t)
        return out

    def has_any_ship_track(self, now, require_position=True):
        """是否存在任何敌 USV 航迹（含丢失但有位置的）。composition-agnostic。"""
        for t in self.tracks.values():
            if t.is_ship and (t.has_position or not require_position):
                return True
        return False


# ════════════════════════════════════════════════════════════════
# CoverageMap —— 轻量确定性 coverage / information map（V5）
# ════════════════════════════════════════════════════════════════
class CoverageMap:
    """确定性 coverage grid。

    - 格子数量由 battlefield geometry 固定（不随 fleet size 变）。
    - 每格维护 last_covered（最近一次被白方感知覆盖的时间）。
    - 突破相关权重：靠近突破线 x 越小 → 权重越高（保护突破相关区域优先）。
    - 供 GLOBAL_SEARCH（mission-unresolved 全局重搜）与 coverage_quality 统计使用。
    """

    def __init__(self):
        self.nx = max(1, int((COVERAGE_X1 - COVERAGE_X0) / COVERAGE_CELL))
        self.ny = max(1, int((COVERAGE_Y1 - COVERAGE_Y0) / COVERAGE_CELL))
        self.last_covered = {}
        self._weight = {}
        for ix in range(self.nx):
            x = COVERAGE_X0 + (ix + 0.5) * COVERAGE_CELL
            w = 1.0 + 2.0 * max(0.0, 1.0 - min(x, 150_000.0) / 150_000.0)
            for iy in range(self.ny):
                self._weight[(ix, iy)] = w

    def _cell(self, x, y):
        ix = int((x - COVERAGE_X0) / COVERAGE_CELL)
        iy = int((y - COVERAGE_Y0) / COVERAGE_CELL)
        ix = max(0, min(self.nx - 1, ix))
        iy = max(0, min(self.ny - 1, iy))
        return (ix, iy)

    def _center(self, ix, iy):
        return (COVERAGE_X0 + (ix + 0.5) * COVERAGE_CELL,
                COVERAGE_Y0 + (iy + 0.5) * COVERAGE_CELL)

    def mark_covered(self, x, y, t, radius=65_000.0):
        """感知点覆盖其周边 cells（UAV 60km 雷达 + 余量）。"""
        c = self._cell(x, y)
        cells = [c]
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                nx, ny = c[0] + dx, c[1] + dy
                if 0 <= nx < self.nx and 0 <= ny < self.ny and (nx, ny) != c:
                    cells.append((nx, ny))
        for cc in cells:
            self.last_covered[cc] = max(self.last_covered.get(cc, -1e18), t)

    def best_unobserved(self, t, k=1):
        """返回优先级最高的 k 个陈旧/未覆盖格 (center, priority)。"""
        scored = []
        for (ix, iy), w in self._weight.items():
            age = t - self.last_covered.get((ix, iy), -1e18)
            if age < COVERAGE_STALE:
                continue
            scored.append((age * w, ix, iy))
        scored.sort(key=lambda x: -x[0])
        out = []
        for _, ix, iy in scored[:k]:
            cx, cy = self._center(ix, iy)
            out.append(((cx, cy), self._weight[(ix, iy)]))
        return out

    def coverage_quality(self, t):
        """突破相关区域中"近期被覆盖"比例（0~1）。"""
        if not self._weight:
            return 1.0
        covered = 0
        for (ix, iy), w in self._weight.items():
            age = t - self.last_covered.get((ix, iy), -1e18)
            if age < COVERAGE_STALE:
                covered += 1
        return covered / len(self._weight)


# ════════════════════════════════════════════════════════════════
# FriendlyResourceState —— 统一资源表示（V5，composition-agnostic）
# ════════════════════════════════════════════════════════════════
class FriendlyResourceState:
    """把 /status 白方单位聚合为绝对值 + 比例，供 controller / summary / commander 共用。

    绝对值保留（7 艘就是 7 艘）；同时提供比例（3/4 与 3/15 含义不同）。
    不携带任何 scenario label / 敌方数量先验。
    """
    __slots__ = ("usv_total", "usv_alive", "usv_available", "usv_engaged",
                 "usv_frozen", "available_ratio", "engaged_ratio", "frozen_ratio",
                 "uav_alive", "uav_airborne", "uav_searching", "uav_screening",
                 "uav_reacquiring", "uav_returning", "uav_charging",
                 "available_sensing_ratio", "active_combat_tracks",
                 "lost_high_threat_tracks", "threat_cluster_count",
                 "coverage_quality")

    def __init__(self):
        for f in self.__slots__:
            setattr(self, f, 0.0 if f.endswith("ratio") else 0)

    @classmethod
    def build(cls, obs, usv_ctrl, uav_mgr, tracker, coverage, now):
        rs = cls()
        usv_st = usv_ctrl.state
        rs.usv_total = obs.usv_total
        rs.usv_alive = obs.usv_alive
        rs.usv_available = sum(1 for s in usv_st.values() if s == USVController.AVAILABLE)
        rs.usv_engaged = sum(1 for s in usv_st.values() if s == USVController.LOCKING)
        rs.usv_frozen = sum(1 for s in usv_st.values() if s == USVController.FROZEN)
        rs.available_ratio = (rs.usv_available / rs.usv_alive) if rs.usv_alive else 0.0
        rs.engaged_ratio = (rs.usv_engaged / rs.usv_alive) if rs.usv_alive else 0.0
        rs.frozen_ratio = (rs.usv_frozen / rs.usv_alive) if rs.usv_alive else 0.0

        uav_st = uav_mgr.state
        rs.uav_alive = obs.uav_alive
        rs.uav_airborne = sum(1 for v in uav_st.values()
                              if v in (UAVManager.SEARCH, UAVManager.SCREEN,
                                       UAVManager.REACQUIRE, UAVManager.GLOBAL_SEARCH))
        rs.uav_searching = sum(1 for v in uav_st.values() if v == UAVManager.SEARCH)
        rs.uav_screening = sum(1 for v in uav_st.values() if v == UAVManager.SCREEN)
        rs.uav_reacquiring = sum(1 for v in uav_st.values() if v == UAVManager.REACQUIRE)
        rs.uav_returning = sum(1 for v in uav_st.values() if v == UAVManager.RETURN)
        rs.uav_charging = sum(1 for v in uav_st.values()
                              if v in (UAVManager.CHARGING, UAVManager.LANDING))
        rs.available_sensing_ratio = (rs.uav_airborne / rs.uav_alive) if rs.uav_alive else 0.0

        rs.active_combat_tracks = sum(1 for t in tracker.tracks.values()
                                      if t.is_ship and t.is_visible(now))
        rs.lost_high_threat_tracks = len(tracker.lost_high_threat(now))
        rs.coverage_quality = coverage.coverage_quality(now) if coverage else 1.0
        return rs

    def describe(self):
        return (f"usv_alive={self.usv_alive} avail={self.available_ratio:.2f} "
                f"engaged={self.engaged_ratio:.2f} frozen={self.frozen_ratio:.2f} | "
                f"uav_alive={self.uav_alive} airborne={self.uav_airborne} "
                f"search={self.uav_searching} screen={self.uav_screening} "
                f"reacq={self.uav_reacquiring} | tracks={self.active_combat_tracks} "
                f"lost_ht={self.lost_high_threat_tracks} cov={self.coverage_quality:.2f}")


# ════════════════════════════════════════════════════════════════
# ThreatClusterBuilder —— 动态威胁聚类（V5，composition-agnostic）
# ════════════════════════════════════════════════════════════════
class ThreatCluster:
    __slots__ = ("id", "names", "ships", "visible", "lost", "avg_conf",
                 "min_x", "friendly_committed", "local_force_ratio",
                 "near_break", "recon_coverage")

    def __init__(self, cid, names, ships, visible, lost, avg_conf, min_x,
                 committed, near_break):
        self.id = cid
        self.names = names
        self.ships = ships
        self.visible = visible
        self.lost = lost
        self.avg_conf = avg_conf
        self.min_x = min_x
        self.friendly_committed = committed
        self.local_force_ratio = (committed / max(1, ships))
        self.near_break = near_break
        self.recon_coverage = "low" if lost > 0 else ("medium" if visible < ships else "high")

    def describe(self):
        return (f"CLUSTER {self.id}: tracks={self.ships} visible={self.visible} "
                f"lost={self.lost} avg_conf={self.avg_conf:.2f} "
                f"min_breakthrough_x={int(self.min_x)} "
                f"friendly_committed={self.friendly_committed} "
                f"local_force_ratio={self.local_force_ratio:.2f} "
                f"near_break={str(self.near_break).lower()} "
                f"recon_coverage={self.recon_coverage}")


class ThreatClusterBuilder:
    """轻量确定性聚类：只聚类敌 USV，按 x 距离相近分组（1D 贪心）。

    不固定 LEFT/CENTER/RIGHT，不固定 cluster 数；由当前 track 空间分布自然产生。
    """

    def __init__(self, gap=60_000.0):
        self.gap = gap

    def build(self, tracks, now):
        ships = [t for t in tracks.values()
                 if t.is_ship and t.has_position and t.predicted_position(now) is not None]
        if not ships:
            return []
        ships.sort(key=lambda t: t.predicted_position(now)[0])
        groups = [[ships[0]]]
        for t in ships[1:]:
            px = groups[-1][-1].predicted_position(now)[0]
            tx = t.predicted_position(now)[0]
            if abs(tx - px) <= self.gap:
                groups[-1].append(t)
            else:
                groups.append([t])
        out = []
        for i, g in enumerate(groups):
            names = [t.name for t in g]
            visible = sum(1 for t in g if t.is_visible(now))
            lost = len(g) - visible
            avg_conf = sum(t.point_confidence for t in g) / len(g)
            min_x = min(t.predicted_position(now)[0] for t in g)
            committed = sum(len(t.assigned_usvs) for t in g)
            near = min_x < 120_000.0
            out.append(ThreatCluster(f"cluster_{i + 1}", names, len(g), visible,
                                     lost, avg_conf, min_x, committed, near))
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
                 "engagement_aggressiveness", "overmatch_policy", "recon_mode",
                 "standoff_preference", "uncertainty_tolerance",
                 "coverage_priority", "priority_clusters", "reason")

    def __init__(self, posture="balanced", focus_level=2, emergency_focus_level=3,
                 reserve_usvs=None, reserve_ratio=0.20,
                 threat_bias="breakthrough_eta", priority_tracks=None,
                 uav_mode="search_and_reacquire", uav_priority_tracks=None,
                 recon_aggressiveness=0.6, engagement_aggressiveness=0.7,
                 overmatch_policy="balanced", recon_mode="balanced",
                 standoff_preference="medium", uncertainty_tolerance=0.35,
                 coverage_priority=0.6, priority_clusters=None, reason=""):
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
        self.overmatch_policy = overmatch_policy          # economical|balanced|decisive
        self.recon_mode = recon_mode                      # broad_search|balanced|screen_priority|reacquire_priority
        self.standoff_preference = standoff_preference    # low|medium|high
        self.uncertainty_tolerance = max(0.0, min(1.0, float(uncertainty_tolerance)))
        self.coverage_priority = max(0.0, min(1.0, float(coverage_priority)))
        self.priority_clusters = list(priority_clusters or [])
        self.reason = reason or ""

    def describe(self):
        resv = self.reserve_usvs if self.reserve_usvs is not None else "auto"
        return (f"posture={self.posture} focus={self.focus_level} "
                f"emergency={self.emergency_focus_level} reserve_ratio={self.reserve_ratio:.2f} "
                f"reserve_usvs={resv} "
                f"bias={self.threat_bias} priority={self.priority_tracks} "
                f"uav_mode={self.uav_mode} uav_priority={self.uav_priority_tracks} "
                f"recon={self.recon_aggressiveness:.1f} engage={self.engagement_aggressiveness:.1f} "
                f"overmatch={self.overmatch_policy} recon_mode={self.recon_mode} "
                f"standoff={self.standoff_preference} unc_tol={self.uncertainty_tolerance:.2f} "
                f"cov_pri={self.coverage_priority:.2f} clusters={self.priority_clusters}")

    def describe(self):
        resv = self.reserve_usvs if self.reserve_usvs is not None else "auto"
        return (f"posture={self.posture} focus={self.focus_level} "
                f"emergency={self.emergency_focus_level} reserve_ratio={self.reserve_ratio:.2f} "
                f"reserve_usvs={resv} "
                f"bias={self.threat_bias} priority={self.priority_tracks} "
                f"uav_mode={self.uav_mode} uav_priority={self.uav_priority_tracks} "
                f"recon={self.recon_aggressiveness:.1f} engage={self.engagement_aggressiveness:.1f} "
                f"overmatch={self.overmatch_policy} recon_mode={self.recon_mode} "
                f"standoff={self.standoff_preference} unc_tol={self.uncertainty_tolerance:.2f}")

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
                and abs(self.engagement_aggressiveness - other.engagement_aggressiveness) < 1e-9
                and self.overmatch_policy == other.overmatch_policy
                and self.recon_mode == other.recon_mode
                and self.standoff_preference == other.standoff_preference
                and abs(self.uncertainty_tolerance - other.uncertainty_tolerance) < 1e-9
                and abs(self.coverage_priority - other.coverage_priority) < 1e-9
                and self.priority_clusters == other.priority_clusters)

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
敌方的运动可能不确定或正在机动。预测航迹只是信念，不是真值。
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
当信息质量下降（低置信/高不确定 lost track）：优先考虑 UAV reacquire，而不是直接大量投入 USV；
但若突破风险极高，必须立即拦截。
对已经稳定 engagement 的目标：不要无意义重新分配已锁 USV。

只输出 JSON，不要 markdown。"""

INTENT_SCHEMA_DOC = """输出 JSON StrategicIntent，字段与约束：
{
  "posture": "balanced",                 // cautious | balanced | aggressive
  "focus_level": 2,                      // int 1~3（常规交战每目标攻击者数）
  "emergency_focus_level": 3,            // int 2~4（临近突破高威胁的攻击者数）
  "reserve_ratio": 0.20,                 // float 0~0.5（预备比例 = 预备USV/当前可用USV；
                                         //   规模无关：敌情不明时高，临近突破时可降到 0）
  "overmatch_policy": "balanced",        // economical | balanced | decisive（局部数量优势力度）
  "recon_mode": "balanced",              // broad_search | balanced | screen_priority | reacquire_priority
  "standoff_preference": "medium",       // low | medium | high（交战保持距离偏好）
  "uncertainty_tolerance": 0.35,         // float 0~1（对不确定的容忍度；低=更谨慎提交 USV）
  "threat_bias": "breakthrough_eta",     // breakthrough_eta | nearest | highest_confidence | balanced
  "priority_tracks": ["E3","E7"],        // 只能是 CURRENT TACTICAL STATE 中当前存在的 track id（小规模兼容）
  "uav_mode": "search_and_reacquire",    // broad_search | search_and_reacquire | focused_reacquire
  "uav_priority_tracks": ["E7"],         // 只能是当前存在的 track id
  "recon_aggressiveness": 0.7,           // 0~1（侦察投入程度）
  "engagement_aggressiveness": 0.7,      // 0~1（交战积极程度）
  "coverage_priority": 0.6,              // 0~1（全局覆盖/重搜投入偏好；mission-unresolved 时高）
  "priority_clusters": ["cluster_1"],    // 只能是 THREAT CLUSTERS 中出现的 cluster id（首选）
  "reason": "短文本，仅日志用"
}
注意：
- priority_clusters 只能选战术摘要中 THREAT CLUSTERS 出现的 id；无重点给空数组。
- priority_tracks / uav_priority_tracks 只能选当前存在的 track id（小规模兼容，非主接口）。
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
    OVERMATCH = {"economical", "balanced", "decisive"}
    RECON_MODES = {"broad_search", "balanced", "screen_priority", "reacquire_priority"}
    STANDOFF = {"low", "medium", "high"}

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
    def parse(text, valid_tracks, valid_clusters=None):
        obj = CommanderIntentAdapter.extract_json_object(text)
        if obj is None:
            return None, "malformed_json"
        return CommanderIntentAdapter.validate(obj, valid_tracks, valid_clusters)

    @staticmethod
    def validate(obj, valid_tracks, valid_clusters=None):
        valid_tracks = set(valid_tracks or [])
        valid_clusters = set(valid_clusters or [])
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
            om = str(obj.get("overmatch_policy", "balanced")).strip().lower()
            if om not in CommanderIntentAdapter.OVERMATCH:
                om = "balanced"
            rm = str(obj.get("recon_mode", "balanced")).strip().lower()
            if rm not in CommanderIntentAdapter.RECON_MODES:
                rm = "balanced"
            sp = str(obj.get("standoff_preference", "medium")).strip().lower()
            if sp not in CommanderIntentAdapter.STANDOFF:
                sp = "medium"
            unc = max(0.0, min(1.0, float(obj.get("uncertainty_tolerance", 0.35))))
            cov_pri = max(0.0, min(1.0, float(obj.get("coverage_priority", 0.6))))
            reason = str(obj.get("reason", ""))[:200]

            def clean(lst):
                out = []
                for n in (lst or []):
                    n = str(n).strip()
                    if n and n in valid_tracks and n not in out:
                        out.append(n)
                return out

            def clean_clusters(lst):
                out = []
                for n in (lst or []):
                    n = str(n).strip()
                    if n and n in valid_clusters and n not in out:
                        out.append(n)
                return out

            prio = clean(obj.get("priority_tracks"))
            uprio = clean(obj.get("uav_priority_tracks"))
            clusters = clean_clusters(obj.get("priority_clusters"))
        except Exception:
            return None, "invalid_values"

        intent = StrategicIntent(posture=posture, focus_level=focus,
                                 emergency_focus_level=emg, reserve_usvs=reserve_usvs,
                                 reserve_ratio=reserve_ratio,
                                 threat_bias=bias, priority_tracks=prio, uav_mode=uav_mode,
                                 uav_priority_tracks=uprio, recon_aggressiveness=recon,
                                 engagement_aggressiveness=engage,
                                 overmatch_policy=om, recon_mode=rm,
                                 standoff_preference=sp, uncertainty_tolerance=unc,
                                 coverage_priority=cov_pri, priority_clusters=clusters,
                                 reason=reason)
        return intent, None

    @staticmethod
    def validate_policy(intent, ctx):
        """战略政策校验（doctrine 级，schema 之上）。

        ctx 来自实时态势（AgentMain 计算）：{n_ships, n_uncovered, n_lost_ht,
        breakthrough_imminent, blind(全接触不确定), n_usv_alive, force_ratio}。
        只做安全 clamp（可正常化的），返回 (intent, fallback_reason|None)。
        不改变确定性控制器的不变量，只约束战略偏好。
        """
        if intent is None:
            return None, "no_intent"
        reasons = []
        blind = bool(ctx.get("blind"))
        brk = bool(ctx.get("breakthrough_imminent"))
        # 1) 全接触不确定时不得饿死侦察（信息即能力）
        if blind and intent.recon_aggressiveness < 0.5:
            intent.recon_aggressiveness = max(0.5, intent.recon_aggressiveness)
            reasons.append("recon_floor_when_blind")
        # 2) 突破临近时不得高留预备 / 消极交战
        if brk:
            if intent.reserve_ratio > 0.10:
                intent.reserve_ratio = 0.10
                reasons.append("reserve_cap_when_breakthrough")
            if intent.engagement_aggressiveness < 0.5:
                intent.engagement_aggressiveness = 0.5
                reasons.append("engage_floor_when_breakthrough")
        # 3) 兵力极少且未解决威胁多：不可过度集中（保留覆盖能力）——由 allocator coverage floor
        #    兜底；这里只防止"高不确定 + 极度集中"的极端组合。
        n_usv = int(ctx.get("n_usv_alive", 5))
        n_ships = int(ctx.get("n_ships", 0))
        if intent.overmatch_policy == "decisive" and n_ships > 1 and n_usv < n_ships:
            if intent.focus_level > 2:
                intent.focus_level = 2
                reasons.append("focus_cap_when_outnumbered")
        # 4) V5: GLOBAL_REACQUIRE / mission-unresolved → recon floor（覆盖优先于提交）
        if ctx.get("mission") == MISSION_GLOBAL_REACQUIRE:
            if intent.recon_aggressiveness < 0.7:
                intent.recon_aggressiveness = 0.7
                reasons.append("recon_floor_global_reacquire")
            intent.coverage_priority = max(intent.coverage_priority, 0.7)
            reasons.append("coverage_boost_global_reacquire")
        # 5) V5: 兵力极低（endgame）→ 限制 decisive overmatch（不可过度集中）
        if 0 < n_usv <= 2 and intent.overmatch_policy == "decisive" \
                and intent.engagement_aggressiveness > 0.8:
            intent.engagement_aggressiveness = 0.8
            reasons.append("engage_cap_when_critically_low")
        return intent, (",".join(reasons) if reasons else None)


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
        n_dead = sum(1 for s in usv_st.values() if s == USVController.DEAD)
        uav_st = uav_mgr.state
        n_air = sum(1 for v in uav_st.values() if v in (UAVManager.SEARCH, UAVManager.SCREEN, UAVManager.REACQUIRE, UAVManager.GLOBAL_SEARCH))
        n_rtb = sum(1 for v in uav_st.values() if v == UAVManager.RETURN)
        n_chg = sum(1 for v in uav_st.values() if v in (UAVManager.CHARGING, UAVManager.LANDING))
        n_loiter = sum(1 for v in uav_st.values() if v == UAVManager.SAFE_LOITER)

        tracks = list(tracker.tracks.values())
        tracks.sort(key=lambda t: -self.allocator.threat_score(t, now))
        lost_ht = tracker.lost_high_threat(now)
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
        L.append(f"usv_alive={obs.usv_alive} usv_available={n_avail} usv_engaged={n_lock} "
                 f"usv_frozen={n_frz}")
        L.append(f"uav_airborne={n_air + n_rtb} uav_searching={n_air} uav_returning={n_rtb} "
                 f"uav_charging={n_chg} uav_safe_loiter={n_loiter}")
        L.append("")
        L.append("KNOWN ENEMY TRACKS:")
        if not tracks:
            L.append("(none detected)")
        else:
            n_ships = sum(1 for t in tracks if t.is_ship)
            n_uavs_t = sum(1 for t in tracks if not t.is_ship)
            L.append(f"count={len(tracks)} ships={n_ships} uavs={n_uavs_t} visible={n_vis} "
                     f"lost={len(tracks) - n_vis} engaged={n_eng} unassigned={n_un}")
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
            L.append(f"  confidence={t.confidence:.2f} point_conf={t.point_confidence:.2f} "
                     f"maneuver={t.maneuver_score:.2f}")
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
        # MANEUVER / uncertainty aggregate（V3）
        high_man = [t.name for t in tracks if t.maneuver_score > 0.5]
        high_unc = [t.name for t in tracks
                    if t.has_position and t.uncertainty(now) > 20000.0]
        L.append("MANEUVER:")
        L.append(f"high_maneuver_tracks={high_man}")
        L.append(f"high_uncertainty_tracks={high_unc}")
        L.append(f"avg_point_conf={sum(t.point_confidence for t in tracks) / len(tracks) if tracks else 0:.2f}")
        L.append("")
        # ENGAGEMENT aggregate（V3）
        first_lock_candidates = [t.name for t in tracks
                                 if t.is_ship and t.is_visible(now) and not t.engaged
                                 and t.has_position]
        near_break = [t.name for t in tracks
                      if t.is_ship and t.engaged and t.has_position
                      and t.predicted_position(now) is not None]
        L.append("ENGAGEMENT:")
        L.append(f"first_lock_candidates={first_lock_candidates}")
        L.append(f"targets_engaged={n_eng} targets_unassigned={n_un}")
        L.append("")
        # RECON aggregate（V3）: sensing demand 由当前态势推出
        reacquire_demand = len(lost_ht)
        screen_demand = sum(1 for t in tracks if t.is_ship and t.is_visible(now)
                            and len(t.assigned_usvs) < 2)
        L.append("RECON:")
        L.append(f"lost_high_threat_tracks={reacquire_demand} reacquire_demand={reacquire_demand}")
        L.append(f"screen_demand={screen_demand} search_needed={int(obs.enemy_visible == 0)}")
        L.append(f"uav_airborne={n_air + n_rtb + n_loiter}")
        L.append("")
        # FORCE aggregate（V3）
        usv_alive = obs.usv_alive
        available_ratio = (n_avail / usv_alive) if usv_alive else 0.0
        engaged_ratio = (n_lock / usv_alive) if usv_alive else 0.0
        L.append("FORCE:")
        L.append(f"usv_alive={usv_alive} usv_available={n_avail} usv_engaged={n_lock} "
                 f"available_ratio={available_ratio:.2f} engaged_ratio={engaged_ratio:.2f}")
        L.append("")
        # THREAT CLUSTERS（V3，简单确定性聚类：按 x 相近 + 类型分组）
        clusters = self._threat_clusters(tracks, now)
        if clusters:
            L.append("THREAT CLUSTERS:")
            for ci, c in enumerate(clusters, 1):
                L.append(f"CLUSTER {ci}: tracks={len(c['names'])} ships={c['ships']} "
                         f"high_threat={c['high_threat']} avg_conf={c['avg_conf']:.2f} "
                         f"friendly_committed={c['committed']} near_break={str(c['near_break']).lower()}")
        L.append("")
        L.append("CURRENT COMMANDER INTENT:")
        L.append(intent.describe())
        return "\n".join(L), [t.name for t in tracks]

    def build_v5(self, obs, tracker, usv_ctrl, uav_mgr, intent, resource,
                 clusters, coverage, mission, now):
        """V5 variable-cardinality 摘要：token 预算与兵力数量近似恒定（聚类 + top-K + 聚合）。

        只打包公平观测 + 聚合资源/聚类/关键航迹；不含 scenario label / 敌方总数先验。
        返回 (text, valid_tracks, valid_clusters)。
        """
        tracks = list(tracker.tracks.values())
        tracks.sort(key=lambda t: -self.allocator.threat_score(t, now))
        lost_ht = tracker.lost_high_threat(now)
        K = min(8, len(tracks))
        detail = tracks[:K]

        L = []
        L.append("TIME:")
        L.append(f"sim_time={int(now)}  mission={mission}")
        L.append("")
        L.append("MISSION:")
        L.append("prevent breakthrough")
        L.append("")
        L.append("FRIENDLY RESOURCE SUMMARY:")
        L.append(resource.describe())
        L.append(f"usv_total={obs.usv_total} uav_total={obs.uav_total}")
        L.append("")
        L.append("COVERAGE:")
        L.append(f"coverage_quality={resource.coverage_quality:.2f} "
                 f"airborne_recon={resource.uav_airborne}/{resource.uav_alive}")
        L.append("")
        if clusters:
            L.append("THREAT CLUSTERS:")
            for c in clusters:
                L.append(c.describe())
        else:
            L.append("THREAT CLUSTERS: (none)")
        L.append("")
        L.append("KNOWN ENEMY TRACKS:")
        if not tracks:
            L.append("(none detected)")
        else:
            n_ships = sum(1 for t in tracks if t.is_ship)
            n_uavs_t = sum(1 for t in tracks if not t.is_ship)
            n_vis = sum(1 for t in tracks if t.is_visible(now))
            n_eng = sum(1 for t in tracks if t.engaged)
            L.append(f"count={len(tracks)} ships={n_ships} uavs={n_uavs_t} visible={n_vis} "
                     f"lost={len(tracks) - n_vis} engaged={n_eng}")
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
            L.append(f"  confidence={t.confidence:.2f} point_conf={t.point_confidence:.2f} "
                     f"maneuver={t.maneuver_score:.2f}")
            L.append(f"  threat={self.allocator.threat_score(t, now):.2f}")
            L.append(f"  attackers={len(t.assigned_usvs)}  engaged={str(t.engaged).lower()}")
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
        high_man = [t.name for t in tracks if t.maneuver_score > 0.5]
        high_unc = [t.name for t in tracks
                    if t.has_position and t.uncertainty(now) > 20000.0]
        L.append("MANEUVER:")
        L.append(f"high_maneuver_tracks={high_man}")
        L.append(f"high_uncertainty_tracks={high_unc}")
        L.append("")
        L.append("RECON:")
        L.append(f"lost_high_threat_tracks={len(lost_ht)} "
                 f"screen_demand={resource.uav_screening} "
                 f"reacquire_demand={len(lost_ht)} "
                 f"search_needed={int(obs.enemy_visible == 0)}")
        L.append("")
        L.append("CURRENT COMMANDER INTENT:")
        L.append(intent.describe())
        valid_clusters = [c.id for c in clusters]
        return "\n".join(L), [t.name for t in tracks], valid_clusters

    @staticmethod
    def _threat_clusters(tracks, now, gap=60_000.0):
        """确定性轻量聚类：把敌舰（只聚类 ship，避免敌 UAV 撑高）按 x 距离相近聚簇。"""
        ships = [t for t in tracks if t.is_ship and t.has_position
                 and t.predicted_position(now) is not None]
        if not ships:
            return []
        ships.sort(key=lambda t: t.predicted_position(now)[0])
        clusters = []
        cur = [ships[0]]
        for t in ships[1:]:
            px = cur[-1].predicted_position(now)[0]
            tx = t.predicted_position(now)[0]
            if abs(tx - px) <= gap:
                cur.append(t)
            else:
                clusters.append(cur)
                cur = [t]
        clusters.append(cur)
        out = []
        for c in clusters:
            names = [t.name for t in c]
            ships_n = len(c)
            high = sum(1 for t in c if t.point_confidence >= 0.5)
            avg_conf = sum(t.confidence for t in c) / len(c)
            committed = sum(len(t.assigned_usvs) for t in c)
            near = any(t.predicted_position(now)[0] < 120000.0 for t in c)
            out.append({"names": names, "ships": ships_n, "high_threat": high,
                        "avg_conf": avg_conf, "committed": committed, "near_break": near})
        return out


# ════════════════════════════════════════════════════════════════
# LLMCommander —— 后台异步 commander（V4: 可观测 source + 审计 + 状态驱动触发 + 滞回）
# ════════════════════════════════════════════════════════════════
class LLMCommander:
    """后台线程 + 锁。主循环每步调用 maybe_request()；若满足间隔且无 in-flight，
    则快照当前摘要交给后台线程调 LLM，完成后原子更新 latest_intent。
    主循环始终使用 last_valid intent（get_intent()），绝不等待 LLM。

    V4 新增:
      - commander_source 可观测：deepseek / provider_fallback / parse_fallback / default_intent
      - 结构化审计记录 audit[]（不含隐藏思维链）
      - 状态驱动触发：仅 material state change 或优先事件触发；带最小间隔与滞回
      - 滞回：新 intent 若与当前战略字段相同（不含 reason）则不覆盖（避免振荡）
      - 战略政策校验（validate_policy）：schema 之上再做 doctrine 级 clamp
    """

    PRIORITY_TRIGGERS = {"first_detect", "friendly_loss", "breakthrough_risk",
                         "multi_frozen", "threat_spike", "lost_high_threat"}

    def __init__(self, enabled=True, skill_text=None, min_interval_sim=MIN_COMMANDER_INTERVAL_SIM,
                 call_fn=None):
        self.enabled = enabled
        self.lock = threading.Lock()
        self.latest_intent = DEFAULT_INTENT
        self.last_source = "default_intent"
        self.last_request_sim = float("-inf")
        self.in_flight = False
        self.min_interval_sim = min_interval_sim
        self.skill_text = skill_text or SkillLoader.FALLBACK_DOCTRINE
        self.call_fn = call_fn or call_commander_llm
        self.stats = {"calls": 0, "responses": 0, "parse_failures": 0,
                      "api_failures": 0, "policy_failures": 0, "no_change": 0,
                      "stale_rejected": 0, "latency_sum": 0.0}
        self.audit = []
        self._last_sig = None
        # V6 stale-response protection: every Commander request carries a monotonic
        # request_id/generation + source_step_id + source_state_signature. A response is
        # accepted ONLY if the state signature has not moved since the request was spawned;
        # otherwise it is rejected and logged as STALE_REJECTED (last_valid_intent kept).
        self._req_counter = 0
        self._latest_observed_sig = None

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

    def get_source(self):
        with self.lock:
            return self.last_source

    def maybe_request(self, now_sim, summary_text, valid_tracks, trigger="periodic",
                      state_sig=None, ctx=None, valid_clusters=None,
                      audit=None, source_step_id=None):
        """状态驱动触发。立即返回（spawn 后台线程），不阻塞。

        V6: records request_id/generation/source_step_id/source_state_signature for
        stale-response rejection and per-step audit C/D capture.
        """
        if not self.enabled:
            return False
        with self.lock:
            # V6: latest observed signature advances every decision round (even when no
            # request fires) so any earlier pending response becomes stale if the state
            # has since changed materially.
            self._latest_observed_sig = state_sig
            if self.in_flight:
                return False
            if now_sim - self.last_request_sim < self.min_interval_sim:
                return False
            # 状态驱动：非优先事件但 state_sig 未变 → 不调用（避免周期空转）
            if trigger not in self.PRIORITY_TRIGGERS and state_sig is not None \
                    and state_sig == self._last_sig:
                return False
            self._last_sig = state_sig
            self.in_flight = True
            self.last_request_sim = now_sim
            self._req_counter += 1
            request_id = self._req_counter
            generation = request_id
        print(f"[COMMANDER REQUEST] t={now_sim:.0f}s trigger={trigger} "
              f"request_id={request_id} source_step={source_step_id}")
        t = threading.Thread(target=self._worker,
                             args=(now_sim, summary_text, list(valid_tracks), trigger,
                                   ctx, list(valid_clusters or []),
                                   request_id, generation, source_step_id, state_sig, audit),
                             daemon=True)
        t.start()
        return True

    def _worker(self, now_sim, summary_text, valid_tracks, trigger, ctx, valid_clusters,
                request_id, generation, source_step_id, source_state_signature, audit):
        t0 = time.time()
        system = self.build_system_prompt()
        user = f"CURRENT TACTICAL STATE:\n\n{summary_text}\n\nReturn the next StrategicIntent."
        # 审计 C: exact external LLM request actually sent (no keys/CoT; thinking disabled)
        if audit is not None:
            audit.append(source_step_id, "C", {
                "request_id": request_id, "generation": generation,
                "source_step_id": source_step_id,
                "source_state_signature": [list(x) if isinstance(x, tuple) else x
                                           for x in source_state_signature]
                                           if source_state_signature is not None else None,
                "model": DS_MODEL, "max_tokens": 2000, "thinking_disabled": True,
                "system": system, "user": user,
            })
        raw = self._safe_call(system, user)
        latency = time.time() - t0
        with self.lock:
            self.stats["calls"] += 1
            self.stats["latency_sum"] += latency
            # V6 stale-response protection: accept only if state signature has not moved
            # since the request was spawned.
            cur_sig = self._latest_observed_sig
            stale = (source_state_signature is not None and cur_sig is not None
                     and cur_sig != source_state_signature)
        if stale:
            with self.lock:
                self.stats["stale_rejected"] += 1
                self.in_flight = False
                self.audit.append({
                    "sim_time": now_sim, "trigger": trigger, "source": self.last_source,
                    "request_id": request_id, "source_step_id": source_step_id,
                    "parse_success": False, "policy_success": False,
                    "fallback_reason": "stale_rejected", "intent": None,
                    "latency": round(latency, 2)})
            print(f"[COMMANDER] STALE_REJECTED request_id={request_id} "
                  f"source_step={source_step_id} using=last_valid_intent "
                  f"latency_real={latency:.1f}s")
            if audit is not None:
                audit.append(source_step_id, "D", {
                    "request_id": request_id, "source_step_id": source_step_id,
                    "stale": True, "applied": False, "rejected_reason": "stale_rejected",
                    "raw_text": raw, "parsed": None,
                    "latency": round(latency, 2), "error": None,
                    "source": self.last_source, "sim_time": now_sim})
            return
        if raw is None:
            with self.lock:
                self.stats["api_failures"] += 1
                self.last_source = "provider_fallback"
                self.in_flight = False
                self.audit.append({
                    "sim_time": now_sim, "trigger": trigger, "source": self.last_source,
                    "request_id": request_id, "source_step_id": source_step_id,
                    "parse_success": False, "policy_success": False,
                    "fallback_reason": "api_failure", "intent": None,
                    "latency": round(latency, 2)})
            print(f"[COMMANDER FALLBACK] reason=api_failure using=last_valid_intent "
                  f"latency_real={latency:.1f}s")
            if audit is not None:
                audit.append(source_step_id, "D", {
                    "request_id": request_id, "source_step_id": source_step_id,
                    "stale": False, "applied": False, "rejected_reason": None,
                    "raw_text": None, "parsed": None,
                    "latency": round(latency, 2), "error": "api_failure",
                    "source": self.last_source, "sim_time": now_sim})
            return
        intent, err = CommanderIntentAdapter.parse(raw, valid_tracks, valid_clusters)
        if intent is None:
            with self.lock:
                self.stats["parse_failures"] += 1
                self.last_source = "parse_fallback"
                self.in_flight = False
                self.audit.append({
                    "sim_time": now_sim, "trigger": trigger, "source": self.last_source,
                    "request_id": request_id, "source_step_id": source_step_id,
                    "parse_success": False, "policy_success": False,
                    "fallback_reason": f"parse_error({err})", "intent": None,
                    "latency": round(latency, 2)})
            print(f"[COMMANDER FALLBACK] reason=parse_error({err}) "
                  f"using=last_valid_intent latency_real={latency:.1f}s")
            if audit is not None:
                audit.append(source_step_id, "D", {
                    "request_id": request_id, "source_step_id": source_step_id,
                    "stale": False, "applied": False, "rejected_reason": None,
                    "raw_text": raw, "parsed": None,
                    "latency": round(latency, 2), "error": f"parse_error({err})",
                    "source": self.last_source, "sim_time": now_sim})
            return
        # 战略政策校验（doctrine 级 clamp）
        intent, perr = CommanderIntentAdapter.validate_policy(intent, ctx or {})
        with self.lock:
            if perr:
                self.stats["policy_failures"] += 1
            # 滞回：战略字段与当前相同（不含 reason）→ 不覆盖，避免振荡
            if self.latest_intent == intent:
                self.stats["no_change"] += 1
                self.last_source = "deepseek"
                self.in_flight = False
                self.audit.append({
                    "sim_time": now_sim, "trigger": trigger, "source": self.last_source,
                    "request_id": request_id, "source_step_id": source_step_id,
                    "parse_success": True, "policy_success": perr is None,
                    "fallback_reason": "no_change", "intent": intent.describe(),
                    "latency": round(latency, 2)})
                sim_equiv = latency * SIM_RATE
                print(f"[COMMANDER RESPONSE] (no_change) {intent.describe()} "
                      f"latency_real={latency:.1f}s sim_equiv={sim_equiv:.0f}s")
                if audit is not None:
                    audit.append(source_step_id, "D", {
                        "request_id": request_id, "source_step_id": source_step_id,
                        "stale": False, "applied": False, "rejected_reason": "no_change",
                        "raw_text": raw, "parsed": intent.describe(),
                        "latency": round(latency, 2), "error": None,
                        "source": self.last_source, "sim_time": now_sim})
                return
            self.latest_intent = intent
            self.last_source = "deepseek"
            self.in_flight = False
            self.stats["responses"] += 1
            self.audit.append({
                "sim_time": now_sim, "trigger": trigger, "source": self.last_source,
                "request_id": request_id, "source_step_id": source_step_id,
                "parse_success": True, "policy_success": perr is None,
                "fallback_reason": perr, "intent": intent.describe(),
                "latency": round(latency, 2)})
        sim_equiv = latency * SIM_RATE
        print(f"[COMMANDER RESPONSE] {intent.describe()} reason={intent.reason!r} "
              f"latency_real={latency:.1f}s sim_equiv={sim_equiv:.0f}s")
        if audit is not None:
            audit.append(source_step_id, "D", {
                "request_id": request_id, "source_step_id": source_step_id,
                "stale": False, "applied": True, "rejected_reason": None,
                "raw_text": raw, "parsed": intent.describe(),
                "latency": round(latency, 2), "error": None,
                "source": self.last_source, "sim_time": now_sim})

    def _safe_call(self, system, user):
        try:
            return self.call_fn(system, user)
        except Exception as e:
            print(f"[COMMANDER] LLM call exception: {e}")
            return None


# ════════════════════════════════════════════════════════════════
# ThreatAllocator —— Marginal-Value Allocation（V3）
# ════════════════════════════════════════════════════════════════
class ThreatAllocator:
    """威胁评估 + 边际价值分配（greedy）。

    V3 相对 V1/V2:
      - 敌类型语义（A2）: 只有敌 USV 构成突破/战斗威胁。敌 UAV 是侦察/信息威胁，
        不得进入 USV 分配，也不得用 breakthrough_eta / combat_priority /
        desired_attackers 处理；threat_score 对敌 UAV 封顶为低"信息威胁"值。
      - Marginal-value（E）: 基于 300s/80%/2 命中的击杀时间模型
          expected_kill_time(k) ≈ 750 / k 秒
          marginal_gain(cur) = 1/cur - 1/(cur+1)（cur=0 时为 1.0：必须开始交战）
        每艘可用 USV 分给"边际价值最大"的目标 → 自然出现 1/2/3 attacker，
        不会无条件把所有力量压到单一目标。
      - Low-confidence commitment guard: 低点置信且丢失的航迹 → 优先 UAV reacquire，
        除非突破风险极高必须立即拦截。
      - intent 参数化保持（focus/emergency/reserve/bias/priority/agg）与 V2 兼容。
    """

    MIN_ASSIGN_VALUE = 0.08          # 低于该边际价值不再 commit
    LOW_CONF_GUARD = 0.35            # point_confidence 低于此且丢失 → 不 commit（除非紧急）
    URGENT_X = 90_000.0              # 突破紧急线：低于此无视低置信 guard 强制拦截

    def __init__(self):
        self.low_conf_commitments = 0

    @staticmethod
    def marginal_gain(cur):
        """增加第 cur+1 艘攻击者的边际击杀收益（期望击杀时间 ~750/k s）。"""
        if cur <= 0:
            return 1.0
        return 1.0 / cur - 1.0 / (cur + 1.0)

    def threat_score(self, t, now, intent=None, usvs=None):
        """威胁分。敌 UAV 封顶为低"信息威胁"（不驱动 USV 分配/突破处理）。"""
        if not t.is_ship:
            # 敌 UAV：侦察/信息威胁。可驱动 sensing 推理，但绝不用于 breakthrough/combat 优先级。
            return min(0.35, 0.1 + 0.2 * t.confidence)
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
        # 点置信：机动/一致性差 → 点预测不可信 → 威胁分降（B）
        conf = t.point_confidence
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

    def allocate_usvs(self, tracks, usvs, usv_map, now, intent=None, return_margin=False,
                      candidates=None):
        """边际价值贪心分配。返回 {target_name: [usv_names]}。

        `candidates`: optional list to receive per-iteration {target, value,
        second_value, margin} diagnostics (instrumentation only; does not alter policy).
        """
        usv_pos = {u["name"]: (u["position"][0], u["position"][1])
                   for u in usvs if u.get("is_alive") and u.get("position")}
        available = [name for name, trg in usv_map.items()
                     if trg is None and name in usv_pos]
        if not available:
            return ( {}, None) if return_margin else {}

        focus = intent.focus_level if intent else 2
        emg = intent.emergency_focus_level if intent else 3
        agg = intent.engagement_aggressiveness if intent else 0.5
        emg_x = EMERGENCY_3V1_X * (0.5 + agg)

        # ── V4: 战略字段→确定性参数（bounded strategic authority）──
        # overmatch_policy 缩放边际价值阈值（decisive→更易 3v1；economical→更早收手）
        om = getattr(intent, "overmatch_policy", "balanced") if intent else "balanced"
        om_scale = {"economical": 1.6, "balanced": 1.0, "decisive": 0.6}.get(om, 1.0)
        min_assign = self.MIN_ASSIGN_VALUE * om_scale
        # uncertainty_tolerance 缩放低置信 guard（0→严格 0.55；1→宽松 0.15）
        unc_tol = getattr(intent, "uncertainty_tolerance", 0.35) if intent else 0.35
        guard_threshold = max(0.15, min(0.60, 0.55 - unc_tol))

        # 候选：只有敌 USV（可突破/可被击杀）。
        ships = []
        for name, t in tracks.items():
            if not t.is_ship or not t.has_position or name in _KILLED:
                continue
            ships.append((name, t))

        # 低置信 commit guard（B/E）：丢失且点置信低 → 不让多艘 USV 追旧预测，
        # 除非突破风险极高。优先交给 UAV reacquire。
        def commit_guard(t):
            if t.is_visible(now):
                return False
            if t.point_confidence < guard_threshold:
                pos = t.predicted_position(now)
                if pos is not None and pos[0] < self.URGENT_X:
                    return False          # 极近突破 → 必须拦截
                return True               # 阻止盲目 commit
            return False

        # reserve（同 V2）：非紧急按 reserve_ratio / reserve_usvs
        def _any_urgent():
            for _, t in ships:
                if not commit_guard(t):
                    pos = t.predicted_position(now)
                    if pos is not None and pos[0] < emg_x:
                        return True
            return False

        emergency = _any_urgent()
        reserve = 0
        if intent and not emergency:
            if intent.reserve_usvs is not None:
                reserve = max(0, min(intent.reserve_usvs, len(available)))
            else:
                ratio = getattr(intent, "reserve_ratio", 0.20)
                reserve = int(round(len(available) * ratio))
                reserve = max(0, min(reserve, len(available)))
        if reserve and len(available) <= reserve:
            return ( {}, None) if return_margin else {}
        if reserve:
            available = available[:-reserve]

        # 目标级价值 = 威胁分 × 边际击杀收益 × (1 - 不确定惩罚)
        def target_value(name, t):
            cur = len(t.assigned_usvs)
            if cur >= emg:
                return 0.0
            base = self.threat_score(t, now, intent=intent, usvs=usvs)
            if intent and name in intent.priority_tracks:
                base += 0.3
            mg = self.marginal_gain(cur)
            # 不确定惩罚：点置信低、丢失、机动强 → 边际收益打折扣（除非紧急拦截）
            if not t.is_visible(now) and t.point_confidence < guard_threshold:
                pos = t.predicted_position(now)
                if pos is not None and pos[0] >= self.URGENT_X:
                    mg *= 0.35
            return base * mg

        def _assign_one(target_name, target_pos):
            nonlocal available
            best_usv, bestd = None, float("inf")
            for uname in available:
                ux, uy = usv_pos[uname]
                d = math.hypot(ux - target_pos[0], uy - target_pos[1]) if target_pos else 0.0
                if d < bestd:
                    bestd, best_usv = d, uname
            if best_usv is None:
                return False
            available.remove(best_usv)
            result.setdefault(target_name, []).append(best_usv)
            tracks[target_name].assigned_usvs.add(best_usv)
            if not tracks[target_name].is_visible(now) and \
                    tracks[target_name].point_confidence < guard_threshold:
                self.low_conf_commitments += 1
            return True

        result = {}
        # ── Pass 1：coverage floor ── 每艘值得交战的敌舰至少 1 个攻击者，
        # 避免任何敌舰"无人对抗"自由西进/自由锁定。
        # 排序：突破威胁高的先覆盖；guard 阻止的（低置信丢失且不紧急）跳过。
        for name, t in sorted(ships, key=lambda x: -self.threat_score(x[1], now, intent=intent)):
            if not available:
                break
            if len(t.assigned_usvs) > 0:
                continue
            if commit_guard(t):
                continue
            tpos = t.predicted_position(now)
            if tpos is None:
                continue
            _assign_one(name, tpos)

        # ── Pass 2：marginal concentration ── 用剩余 USV 按边际价值补 2v1/3v1。
        margin = None
        while available:
            best_name, best_val = None, 0.0
            second_val = 0.0
            guarded = []
            for name, t in ships:
                if commit_guard(t):
                    guarded.append((name, t))
                    continue
                cur = len(t.assigned_usvs)
                if cur >= emg:
                    continue
                v = target_value(name, t)
                if v > best_val:
                    second_val = best_val
                    best_val, best_name = v, name
                elif v > second_val:
                    second_val = v
            if best_name is None:
                # 所有候选都被低置信 guard 挡住：若只剩未解决威胁且无任何进行中交战，
                # 允许把最高威胁的那艘压上（防止"最后 1 艘漏网"）。
                active_engagement = any(len(t.assigned_usvs) > 0 for _, t in ships)
                if not active_engagement and guarded:
                    name, t = max(guarded, key=lambda x: self.threat_score(x[1], now, intent=intent))
                    if self.threat_score(t, now, intent=intent) * self.marginal_gain(len(t.assigned_usvs)) >= min_assign:
                        best_name, best_val = name, 0.0
            if best_name is None or best_val < min_assign:
                break
            margin = best_val - second_val if best_val > 0 else 0.0
            if candidates is not None:
                candidates.append({
                    "target": best_name, "value": round(best_val, 4),
                    "second_value": round(second_val, 4),
                    "margin": round(margin, 5),
                    "assigned_after": len(tracks[best_name].assigned_usvs) + 1})
            t = tracks[best_name]
            tpos = t.predicted_position(now)
            if tpos is None or not _assign_one(best_name, tpos):
                break

        return (result, margin) if return_margin else result


# 已判定击沉的敌舰名（AgentMain 每步更新）
_KILLED = set()


# ════════════════════════════════════════════════════════════════
# USVController —— USV 状态机 + Sensor-assisted lock / standoff（V3）
# ════════════════════════════════════════════════════════════════
class USVController:
    """USV 状态: DEAD / FROZEN / LOCKING / INTERCEPTING / AVAILABLE

    铁律（保留）:
      - 分配保持: 已锁定目标绝不切换; 拦截中目标未失效也绝不切换
      - 被敌锁定不后撤(后撤=放弃我方锁定进度, 送死)

    V3 新增（Phase D）:
      - 锁定后/拦截进入 40km 后，收敛到 LOCK_BAND（~37km）保持，而非持续全速逼近。
      - 目标机动导致距离接近锁断(>39km)时收拢；过近(<32km)时回拉。
      - sensor-assisted first lock: 只要有共享观测（track）且进入锁距即锁定，
        无需等自身 35km 雷达。
    """

    DEAD, FROZEN, LOCKING, INTERCEPTING, AVAILABLE = "DEAD", "FROZEN", "LOCKING", "INTERCEPTING", "AVAILABLE"

    def __init__(self):
        self.targets = {}        # usv_name -> track_name or None
        self.state = {}          # usv_name -> 状态名
        self.standoff_count = 0  # 统计（诊断）

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

    def step(self, obs, tracks, legal, alloc_result, events, intent=None, mission=MISSION_NORMAL):
        """返回 (actions, new_targets) 。new_targets 覆盖内部表并回写。"""
        actions = []
        new_targets = {}
        usv_pos = {}
        # GLOBAL_REACQUIRE：可用 USV 排成防御屏列（保持各 USV 自身 y，收敛到屏列 x）
        # standoff band 由 intent.standoff_preference 动态调节（low/medium/high）
        if intent is not None:
            sp = getattr(intent, "standoff_preference", "medium")
            if sp == "high":
                band_mid, band_inner, band_outer = 35_500.0, 31_000.0, 37_500.0
            elif sp == "low":
                band_mid, band_inner, band_outer = 31_500.0, 27_000.0, 36_000.0
            else:
                band_mid, band_inner, band_outer = LOCK_BAND_MID, LOCK_BAND_INNER, LOCK_BAND_OUTER
        else:
            band_mid, band_inner, band_outer = LOCK_BAND_MID, LOCK_BAND_INNER, LOCK_BAND_OUTER

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
                        # 锁定后 standoff：保持 LOCK_BAND 包络，不持续全速逼近
                        actions.append(self._standoff_move(name, pos, tpos, band_mid, band_inner, band_outer))
                continue

            if st == self.FROZEN:
                new_targets[name] = self.targets.get(name)
                continue

            cur = self.targets.get(name)
            if cur is not None:
                t = tracks.get(cur)
                # 目标真正消失（航迹已删除/已击沉）才释放；stale 但仍在表的继续压（V3）
                if t is None or cur in _KILLED:
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
                # AVAILABLE: 东向宽前沿（含 reserve 船，继续向东巡逻，可机会锁定自卫）。
                # GLOBAL_REACQUIRE：排成防御屏列（保持各 USV 自身 y，收敛到屏列 x），
                # 避免聚集/避免散落到无关区域，保护突破相关区域，等待 UAV 重搜。
                if mission == MISSION_GLOBAL_REACQUIRE:
                    actions.append(self._move(name, pos, (SCREEN_X, pos[1])))
                else:
                    actions.append(self._move(name, pos, (pos[0] + 100_000, pos[1]) if pos else None))
                continue

            t = tracks.get(cur)
            if t is None:
                new_targets[name] = None
                actions.append(self._move(name, pos, (pos[0] + 100_000, pos[1]) if pos else None))
                continue
            tpos = t.predicted_position(obs.now)
            if not t.has_position or tpos is None:
                # 仅方位/无位置 → 无法拦截，退回巡逻（机会锁定仍可救场）
                new_targets[name] = None
                actions.append(self._move(name, pos, (pos[0] + 100_000, pos[1]) if pos else None))
                continue
            dist = math.hypot(tpos[0] - pos[0], tpos[1] - pos[1])

            if dist < LOCK_RANGE and legal.can_lock(name, cur):
                actions.append((f"{name} 锁定 {cur}", "lock"))
            else:
                # 目标已丢失（stale）→ 收紧到自身雷达内（~34km），便于自探测重锁；
                # 目标可见 → 用 intent 决定的 standoff band。
                if not t.is_visible(obs.now):
                    actions.append(self._standoff_move(name, pos, tpos, 34_000.0, 30_000.0, 36_500.0))
                elif dist < LOCK_RANGE:
                    actions.append(self._standoff_move(name, pos, tpos, band_mid, band_inner, band_outer))
                else:
                    actions.append(self._move(name, pos, tpos))

        self.targets = new_targets
        return actions

    def _standoff_move(self, name, pos, tpos, band_mid, band_inner, band_outer):
        """收敛到 band_mid 的保持机动。"""
        dist = math.hypot(tpos[0] - pos[0], tpos[1] - pos[1])
        if dist < 1.0:
            return (f"{name} 移动 target_speed={USV_SPEED:.1f} target_course=90.0", "move")
        if dist >= band_outer:
            crs = bearing_to(pos, tpos)                 # 收拢
        elif dist <= band_inner:
            # 回拉到 band（径向向外一点）
            scale = band_mid / dist
            wp = (tpos[0] + (pos[0] - tpos[0]) * scale,
                  tpos[1] + (pos[1] - tpos[1]) * scale)
            crs = bearing_to(pos, wp)
        else:
            # 在带内：向 LOS 上 band_mid 点收敛（微调保持）
            scale = band_mid / dist
            wp = (tpos[0] + (pos[0] - tpos[0]) * scale,
                  tpos[1] + (pos[1] - tpos[1]) * scale)
            crs = bearing_to(pos, wp)
        self.standoff_count += 1
        return (f"{name} 移动 target_speed={USV_SPEED:.1f} target_course={crs:.1f}", "move")

    def _opportunistic_lock(self, name, pos, tracks, legal, obs):
        if pos is None:
            return None
        best, best_key = None, None
        for tname, t in tracks.items():
            if tname in _KILLED or not t.has_position:
                continue
            if not t.is_ship:
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
# UAVManager —— Dynamic Sensor Manager（V3）
# ════════════════════════════════════════════════════════════════
class UAVManager:
    """UAV 状态: ON_SHIP / SEARCH / SCREEN / REACQUIRE / RETURN / LANDING /
                 CHARGING / SAFE_LOITER

    V3 相对 V1/V2:
      - A1: SAFE_LOITER —— 无回收 USV（含机库占用）时进入安全盘旋，**不再沿旧航向
        飞出西边界**。电量/降落安全仍是硬不变量，Commander 不可覆盖。
      - C: 动态感知角色 SEARCH / SCREEN / REACQUIRE：
          * REACQUIRE 只针对敌 USV（突破威胁）lost track，region sweep 而非点追；
          * SCREEN 为未交战/需 first-lock 的敌舰维持前向共享感知；
          * SEARCH 覆盖未知区域；数量全部动态，不写死分配数/扇区数。
      - 敌 UAV 不进入 reacquire（A2，不构成突破威胁）。
    """

    ON_SHIP, SEARCH, SCREEN, REACQUIRE, RETURN, LANDING, CHARGING, SAFE_LOITER, GLOBAL_SEARCH = \
        "ON_SHIP", "SEARCH", "SCREEN", "REACQUIRE", "RETURN", "LANDING", "CHARGING", "SAFE_LOITER", "GLOBAL_SEARCH"

    SCREEN_RANGE = 50_000.0     # screen 维持距离（目标 ~50km，落在 60km 前向雷达内）
    LOITER_R = 20_000.0         # SAFE_LOITER 盘旋半径
    LOITER_ANCHOR_X = 150_000.0 # 无存活 USV 时的安全盘旋锚点 x（东向安全区）
    SWEEP_LEGS = 8              # region sweep 方向数

    def __init__(self, enabled=True):
        self.enabled = enabled
        self.state = {}
        self.reacquire_lock = {}   # track_name -> uav_name
        self.search_dir = {}       # uav_name -> +1(顺时针) / -1(逆时针)
        self.sweep_step = {}       # uav_name -> int (region sweep 相位)
        self.screen_target = {}    # uav_name -> track_name (正在 screen 的目标)
        self.reacquire_attempts = 0

    def step(self, obs, tracker, legal, events, intent=None, threat_fn=None,
             coverage=None, mission=MISSION_NORMAL):
        if not self.enabled:
            return []
        tracks = tracker.tracks
        actions = []
        now = obs.now
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

        # 感知覆盖：所有存活 UAV 位置更新 coverage map（V5）
        if coverage is not None:
            for u in obs.uavs:
                if u.get("is_alive") and not u.get("is_at_usv") and u.get("position"):
                    coverage.mark_covered(u["position"][0], u["position"][1], now)

        recon = intent.recon_aggressiveness if intent else 0.6
        focus = intent.focus_level if intent else 2

        # 感知需求（每步动态计算，规模无关）
        reacquire_targets = tracker.reacquire_candidates(now)      # 仅敌 USV，丢失高威胁
        if threat_fn:
            reacquire_targets = sorted(reacquire_targets, key=lambda t: -threat_fn(t, now))
        screen_targets = [t for t in tracks.values()
                          if t.is_ship and t.is_visible(now) and t.has_position
                          and len(t.assigned_usvs) < focus]        # 需 first-lock / 补火力
        screen_targets.sort(key=lambda t: -(threat_fn(t, now) if threat_fn else t.point_confidence))
        search_needed = obs.enemy_visible == 0

        # GLOBAL_SEARCH demand：mission-unresolved 且无可用作战航迹（V5）
        global_search = (mission == MISSION_GLOBAL_REACQUIRE)

        # 清理失效 reacquire_lock
        for trk in list(self.reacquire_lock):
            uavn = self.reacquire_lock[trk]
            if not any(uv.get("name") == uavn and uv.get("is_alive") and not uv.get("is_at_usv")
                       for uv in obs.uavs):
                del self.reacquire_lock[trk]

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
            anchor = self._loiter_anchor(usv_info)

            # ---- 在母舰上（充电中） ----
            if at_usv:
                if st in (None, self.ON_SHIP, self.CHARGING):
                    self.state[name] = self.CHARGING
                need_search = len(reacquire_targets) > 0 or obs.enemy_visible == 0 or recon >= 0.8
                if batt >= UAV_BATTERY_TOTAL * UAV_RECHARGE_THRESHOLD and need_search:
                    home = u.get("home_name")
                    if legal.can_launch(name, home):
                        actions.append(self._launch(name, home))
                        events.append(("UAV RELAUNCH", name))
                        self.state[name] = self.SEARCH
                continue

            if pos is None:
                continue

            # ---- 电量安全（硬不变量，不允许 Commander 覆盖）----
            if recovery is not None:
                est_ret = recv_d / UAV_FLY_SPEED
                if batt < est_ret + UAV_SAFETY_MARGIN:
                    if st != self.RETURN:
                        events.append(("UAV RTB", f"{name}(电量{batt:.0f}<{est_ret:.0f}+{UAV_SAFETY_MARGIN:.0f})"))
                    self.state[name] = self.RETURN
            else:
                # 无回收舰：不得因 est_ret=inf 强行 RTB（A1 修复）。
                # 电量极低且无回收 → SAFE_LOITER（保持安全区，能再找回收就回 RETURN）
                if batt < UAV_BATTERY_TOTAL * 0.10 and st != self.SAFE_LOITER:
                    self.state[name] = self.SAFE_LOITER

            st = self.state.get(name, self.SEARCH)

            # ---- RETURN / LANDING ----
            if st == self.RETURN:
                if recovery is None:
                    self.state[name] = self.SAFE_LOITER   # 回收舰消失 → 安全盘旋
                    actions.append(self._safe_loiter_fly(name, pos, anchor))
                    continue
                rpos = None
                for ui in usv_info:
                    if ui["name"] == recovery:
                        rpos = ui["pos"]
                        break
                if rpos is None:
                    self.state[name] = self.SAFE_LOITER
                    actions.append(self._safe_loiter_fly(name, pos, anchor))
                    continue
                dist = math.hypot(rpos[0] - pos[0], rpos[1] - pos[1])
                if dist <= UAV_RTB_RANGE_KM and legal.can_land(name, recovery):
                    actions.append((f"{name} 降落到 {recovery}", "land_uav"))
                    self.state[name] = self.LANDING
                    events.append(("UAV LAND", f"{name}->{recovery}"))
                elif legal.can_fly(name):
                    actions.append(self._fly(name, pos, rpos))
                continue

            # ---- SAFE_LOITER（A1）：无回收舰时的安全盘旋，不出界 ----
            if st == self.SAFE_LOITER:
                if recovery is not None:
                    self.state[name] = self.RETURN
                    continue
                actions.append(self._safe_loiter_fly(name, pos, anchor))
                continue

            # ---- SEARCH / SCREEN / REACQUIRE / GLOBAL_SEARCH（动态角色分配）----
            if st in (self.SEARCH, self.SCREEN, self.REACQUIRE, self.GLOBAL_SEARCH):
                # 0) GLOBAL_SEARCH：mission-unresolved 且无作战航迹 → 全局 coverage 扫掠
                if global_search:
                    self.state[name] = self.GLOBAL_SEARCH
                    if legal.can_fly(name):
                        actions.append(self._global_search_fly(name, pos, coverage, now, max(1, obs.uav_alive)))
                    continue
                # 1) REACQUIRE 职责（最高优先）：高威胁丢失敌 USV，每航迹最多 1 架
                trk = self._pick_reacquire(name, reacquire_targets)
                if trk is not None:
                    self.state[name] = self.REACQUIRE
                    if self.reacquire_lock.get(trk.name) != name:
                        self.reacquire_attempts += 1
                    self.reacquire_lock[trk.name] = name
                    step_i = self.sweep_step.get(name, 0)
                    self.sweep_step[name] = step_i + 1
                    if legal.can_fly(name):
                        actions.append(self._region_reacquire_fly(name, pos, trk, now, step_i))
                    continue
                # 2) SCREEN 职责：为需 first-lock / 未交战敌舰维持共享感知
                #    recon_mode 调节 screen 门槛（V4，bounded strategic authority）
                rmode = getattr(intent, "recon_mode", "balanced") if intent else "balanced"
                if rmode == "screen_priority":
                    screen_gate = 0.25
                elif rmode == "reacquire_priority":
                    screen_gate = 0.55
                elif rmode == "broad_search":
                    screen_gate = 0.75
                else:
                    screen_gate = 0.45
                scr = self._pick_screen(name, pos, screen_targets)
                if scr is not None and recon >= screen_gate:
                    self.state[name] = self.SCREEN
                    self.screen_target[name] = scr.name
                    if legal.can_fly(name):
                        actions.append(self._screen_fly(name, pos, scr, now))
                    continue
                # 3) SEARCH：覆盖未知区域
                self.state[name] = self.SEARCH
                if legal.can_fly(name):
                    actions.append(self._search_fly(name, pos, max(1, obs.uav_alive)))

        return actions

    def _global_search_fly(self, name, pos, coverage, now, n_airborne):
        """mission-unresolved：飞向优先级最高的陈旧/未覆盖格（动态分配，不固定格数）。"""
        if coverage is None:
            return self._search_fly(name, pos, n_airborne)
        idx = int(name.replace("white_uav", "")) if "white_uav" in name else 0
        targets = coverage.best_unobserved(now, k=max(1, n_airborne))
        if not targets:
            return self._search_fly(name, pos, n_airborne)
        center, _ = targets[idx % len(targets)]
        return self._fly(name, pos, center)

    # ── 角色选择 ──
    def _pick_reacquire(self, uav_name, reacquire_targets):
        for trk in reacquire_targets:
            if trk.name in self.reacquire_lock and self.reacquire_lock[trk.name] != uav_name:
                continue
            return trk
        return None

    def _pick_screen(self, uav_name, pos, screen_targets):
        if not screen_targets:
            return None
        # 已 screen 的目标优先保持；否则选最近的目标
        if self.screen_target.get(uav_name) is not None:
            for t in screen_targets:
                if t.name == self.screen_target[uav_name]:
                    return t
        best, bestd = None, float("inf")
        for t in screen_targets:
            if t.last_position is None:
                continue
            if pos is None:
                return screen_targets[0]
            d = math.hypot(t.last_position[0] - pos[0], t.last_position[1] - pos[1])
            if d < bestd:
                bestd, best = d, t
        return best

    def _loiter_anchor(self, usv_info):
        alive = [ui for ui in usv_info if ui["pos"] is not None]
        if alive:
            cx = sum(ui["pos"][0] for ui in alive) / len(alive)
            cy = sum(ui["pos"][1] for ui in alive) / len(alive)
            return (cx, cy)
        return (self.LOITER_ANCHOR_X, 405000.0)

    # ── 动作生成 ──
    def _launch(self, name, home):
        return (f"{name} 从 {home} 起飞 target_speed={UAV_FLY_SPEED:.1f} target_course=90.0", "launch_uav")

    def _fly(self, name, pos, target_pos):
        if pos is None or target_pos is None:
            crs = 90.0
        else:
            crs = bearing_to(pos, target_pos)
        return (f"{name} 飞行 target_speed={UAV_FLY_SPEED:.1f} target_course={crs:.1f}", "fly")

    def _region_reacquire_fly(self, name, pos, t, now, step_i):
        """region reacquire：先接近信念中心；进入不确定半径后做 expanding sweep。"""
        center, radius = t.predicted_region(now)
        if center is None:
            return self._search_fly(name, pos, 5)
        d = math.hypot(center[0] - pos[0], center[1] - pos[1])
        if d > radius:
            return self._fly(name, pos, center)
        # expanding radial sweep：半径逐步外扩，方向旋转 SWEEP_LEGS 个相位
        r = radius * (1.0 + 0.6 * (step_i % 4))
        ang = math.radians((step_i % self.SWEEP_LEGS) * (360.0 / self.SWEEP_LEGS))
        wp = (center[0] + r * math.sin(ang), center[1] + r * math.cos(ang))
        return self._fly(name, pos, wp)

    def _screen_fly(self, name, pos, t, now):
        """为敌舰维持共享感知：接近至 SCREEN_RANGE 后收敛（保持前向雷达覆盖）。"""
        tpos = t.predicted_position(now)
        if tpos is None:
            return self._search_fly(name, pos, 5)
        d = math.hypot(tpos[0] - pos[0], tpos[1] - pos[1])
        if d > self.SCREEN_RANGE:
            return self._fly(name, pos, tpos)
        # 维持 ~SCREEN_RANGE：径向向外一点（避免贴脸），继续面朝目标
        scale = self.SCREEN_RANGE / d
        wp = (tpos[0] + (pos[0] - tpos[0]) * scale, tpos[1] + (pos[1] - tpos[1]) * scale)
        return self._fly(name, pos, wp)

    def _safe_loiter_fly(self, name, pos, anchor):
        """安全盘旋：围绕锚点做圆，出界回拉。不出西边界/东世界边界。"""
        if pos is None or anchor is None:
            crs = 90.0
            return (f"{name} 飞行 target_speed={UAV_FLY_SPEED:.1f} target_course={crs:.1f}", "fly")
        dx = pos[0] - anchor[0]
        dy = pos[1] - anchor[1]
        dist = math.hypot(dx, dy)
        sgn = self.search_dir.get(name, 1)
        if dist > self.LOITER_R * 1.6:
            self.search_dir[name] = sgn
            return self._fly(name, pos, anchor)
        # 切向绕飞（圆周）
        tp = (pos[0] - dy * sgn, pos[1] + dx * sgn)
        return self._fly(name, pos, tp)

    def _search_fly(self, name, pos, n_uavs):
        d = self.search_dir.get(name, 1)
        if pos is not None:
            if pos[0] >= SEARCH_X_MAX:
                d = -1
            elif pos[0] <= SEARCH_X_MIN:
                d = 1
        self.search_dir[name] = d
        idx = int(name.replace("white_uav", "")) if "white_uav" in name else 0
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
        self._audit = runtime_audit.StepAudit(run_id="pending")

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
        self.metrics = {
            "reacquire_attempts": 0, "reacquire_success": 0,
            "sensor_assisted_locks": 0, "lock_breaks": 0,
            "low_conf_commitments": 0,
            "first_kill_time": None,
            "prev_engaged_names": set(),
            "engaged_since": {},     # track_name -> first lock time
            # V5: GLOBAL_REACQUIRE
            "global_reacquire_entries": 0, "global_reacquire_success": 0,
            "coverage_collapse_events": 0, "active_clusters_max": 0,
        }
        self._ever_saw_enemy = False
        self._ever_saw_ship = False   # V5: 已探测到敌 USV（ship）——GLOBAL_REACQUIRE 前提
        self._prev_visible = None
        self._prev_usv_alive = None
        self._logged_intent_desc = None

        # ── V5: composition-agnostic modules ──
        self.coverage = CoverageMap()
        self.cluster_builder = ThreatClusterBuilder()
        self.resource = FriendlyResourceState()
        self.mission = MISSION_NORMAL
        self._mission = MISSION_NORMAL          # 上一步 mission（用于统计入口/退出）
        self._no_ship_track_since = None        # 无 ship track 起始时刻
        self._in_global_reacquire = False
        self._prev_alloc_margin = None          # allocator 决策裕度（ambiguity trigger）

    # ── 事件聚合 ──
    def _emit_events(self, evs):
        for tag, detail in evs:
            print(f"      [{tag}] {detail}")

    # ── Commander 触发检测 ──
    def _detect_trigger(self, obs, alloc_margin=None):
        if self.mission == MISSION_GLOBAL_REACQUIRE:
            return "global_reacquire"
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
        # V5: allocator 决策歧义（best/second 裕度小）→ 战略偏好介入
        if alloc_margin is not None and 0.0 < alloc_margin < 0.06:
            return "allocator_ambiguity"
        return "periodic"

    def _state_signature(self, obs):
        """紧凑战略状态签名：签名变化 = material state change → 触发 Commander。"""
        tracks = self.tracker.tracks.values()
        ships = [t for t in tracks if t.is_ship and t.has_position]
        n_ships = len(ships)
        n_lost = sum(1 for t in ships if not t.is_visible(obs.now))
        n_engaged = sum(1 for t in ships if t.engaged)
        n_uncovered = sum(1 for t in ships if not t.assigned_usvs)
        min_x = min((t.predicted_position(obs.now)[0] for t in ships
                     if t.predicted_position(obs.now) is not None), default=400000)
        brk_bucket = 0 if min_x > 150000 else (1 if min_x > 90000 else 2)
        conf = [t.point_confidence for t in ships]
        avg_conf = (sum(conf) / len(conf)) if conf else 1.0
        unc = sum(1 for t in ships if t.uncertainty(obs.now) > 20000.0)
        usv = obs.usv_alive
        mission_bucket = {"NORMAL_COMBAT": 0, "GLOBAL_REACQUIRE": 1,
                          "TERMINAL": 2}.get(self.mission, 0)
        cov_bucket = int(round(self.coverage.coverage_quality(obs.now) * 4))
        return (usv, n_ships, n_lost, n_engaged, n_uncovered, brk_bucket,
                round(avg_conf, 1), min(3, unc), obs.enemy_visible > 0,
                mission_bucket, cov_bucket)

    def _commander_ctx(self, obs):
        """给战略政策校验用的态势上下文。"""
        tracks = self.tracker.tracks.values()
        ships = [t for t in tracks if t.is_ship and t.has_position]
        n_ships = len(ships)
        n_uncovered = sum(1 for t in ships if not t.assigned_usvs)
        n_lost_ht = len(self.tracker.lost_high_threat(obs.now))
        brk = any(t.predicted_position(obs.now) is not None and
                  t.predicted_position(obs.now)[0] < 90_000.0 for t in ships)
        confs = [t.point_confidence for t in ships]
        blind = bool(ships) and (sum(confs) / len(confs)) < 0.4
        return {"n_usv_alive": obs.usv_alive, "n_ships": n_ships,
                "n_uncovered": n_uncovered, "n_lost_ht": n_lost_ht,
                "breakthrough_imminent": brk, "blind": blind,
                "mission": self.mission,
                "coverage_quality": self.coverage.coverage_quality(obs.now)}

    def _record_stats(self, obs, events):
        if self.stats["first_detection"] is None:
            if any(e[0] == "DETECT" for e in events) or obs.enemy_visible > 0:
                self.stats["first_detection"] = obs.now
        if self.stats["first_lock"] is None and any(u.get("is_locking") for u in obs.usvs):
            self.stats["first_lock"] = obs.now

        # V5: coverage collapse 检测（NORMAL_COMBAT 下空中侦察 < 1 且覆盖质量掉）
        if self.mission == MISSION_NORMAL and self.resource.uav_airborne < 1 \
                and self.coverage.coverage_quality(obs.now) < 0.3:
            self.metrics["coverage_collapse_events"] += 1

        # ── V3 指标 ──
        # 1) 交战集合变化：新 lock = 记录锁距与首锁时间；消失 = 可能 lock break / kill
        engaged_now = set()
        for u in obs.usvs:
            if u.get("is_locking") and u.get("locking_unit"):
                engaged_now.add(u["locking_unit"])
                if u["locking_unit"] not in self.metrics["engaged_since"]:
                    self.metrics["engaged_since"][u["locking_unit"]] = obs.now
                # 首杀时间
                if self.metrics["first_kill_time"] is None:
                    pass
        # 2) sensor-assisted lock：锁距 > 35km（超出自身雷达 → 靠共享感知首次锁定）
        for u in obs.usvs:
            if u.get("is_locking") and u.get("locking_unit") and u.get("position"):
                t = self.tracker.tracks.get(u["locking_unit"])
                if t is not None and t.has_position:
                    tpos = t.predicted_position(obs.now)
                    up = u["position"]
                    if tpos is not None:
                        d = math.hypot(tpos[0] - up[0], tpos[1] - up[1])
                        if d > 35_000.0:
                            self.metrics["sensor_assisted_locks"] += 1
                            break  # 每步最多计一次（避免重复累计）
        # 3) reacquire success：丢失敌舰航迹重新可见（此前有 UAV 在 reacquire 该 track）
        active_names = {e.get("name") for e in obs.active}
        for tname in list(self.uav_mgr.reacquire_lock.keys()):
            if tname in active_names and tname in self.tracker.tracks:
                self.metrics["reacquire_success"] += 1
                del self.uav_mgr.reacquire_lock[tname]
        # reacquire attempts：来自 UAVManager 统计（进入 REACQUIRE 的次数）
        self.metrics["reacquire_attempts"] = self.uav_mgr.reacquire_attempts
        self.metrics["low_conf_commitments"] = self.allocator.low_conf_commitments

        if obs.ended and self.stats["victory_time"] is None:
            self.stats["victory_time"] = obs.now
            self.stats["result"] = obs.result

        # first kill time（KILL 事件）
        for e in events:
            if e[0] == "KILL" and self.metrics["first_kill_time"] is None:
                self.metrics["first_kill_time"] = obs.now

    def _compute_mission(self, obs):
        """V5 mission state：NORMAL_COMBAT / GLOBAL_REACQUIRE / TERMINAL。

        GLOBAL_REACQUIRE 触发条件（不依赖敌方总数）：
          /result 未结束
          AND 无可靠 hostile USV track（可见或丢失但有位置）
          AND 无仍在有效锁定链中的 hostile combat target
          AND 已曾探测过敌 USV（避免黑方 UAV 探测就把开局算成重搜）
          且持续 GLOBAL_REACQUIRE_DELAY 以上（滞回，防抖动）。
        """
        if obs.ended:
            self._no_ship_track_since = None
            return MISSION_TERMINAL
        has_track = self.tracker.has_any_ship_track(obs.now, require_position=True)
        has_lock = any(u.get("is_locking") and u.get("locking_unit") for u in obs.usvs)
        if not has_track and not has_lock and self._ever_saw_ship:
            if self._no_ship_track_since is None:
                self._no_ship_track_since = obs.now
            if obs.now - self._no_ship_track_since >= GLOBAL_REACQUIRE_DELAY:
                return MISSION_GLOBAL_REACQUIRE
        else:
            self._no_ship_track_since = None
        return MISSION_NORMAL

    def _update_mission_metrics(self):
        if self._mission != self.mission:
            if self.mission == MISSION_GLOBAL_REACQUIRE:
                self.metrics["global_reacquire_entries"] += 1
                self._in_global_reacquire = True
            elif self._in_global_reacquire and self.mission == MISSION_NORMAL:
                # 从 GLOBAL_REACQUIRE 恢复到 NORMAL（重新探测到作战航迹）→ 成功
                self.metrics["global_reacquire_success"] += 1
                self._in_global_reacquire = False
        self._mission = self.mission

    def _update_coverage_from_usvs(self, obs):
        for u in obs.usvs:
            if u.get("is_alive") and u.get("position"):
                self.coverage.mark_covered(u["position"][0], u["position"][1], obs.now)

    # ── 单步 ──
    def step_once(self):
        wall_t0 = time.time()
        st = self.client.status()
        if not isinstance(st, dict):
            return False
        now = parse_sim_time(st.get("局内时间", "00:00:00"))
        obs = Obs(st, now)
        legal_raw = self.client.legal_actions()
        legal = LegalSet(legal_raw) if isinstance(legal_raw, dict) else LegalSet({})

        # 审计 A: raw legal HTTP observation（/status + /legal_actions；/obs 未被 Agent 使用）
        rec = self._audit.new_step(obs.now, wall_t0)
        if rec is not None:
            rec.set_A(st, None, legal_raw)

        # 航迹 + 事件
        events = self.tracker.update(obs)
        self.tracker.reconcile_assigned(obs, self.usv_ctrl.targets)
        kill_evs, killed = self.tracker.kill_detect(obs, self.prev_black_killed)
        events += kill_evs
        _KILLED.update(killed)
        self.prev_black_killed = obs.black_killed

        # V5: mission state + coverage map（USV 感知也标记覆盖）
        self.mission = self._compute_mission(obs)
        self._update_mission_metrics()
        self._update_coverage_from_usvs(obs)

        # 威胁分配（intent 参数化）
        self.intent = self.commander.get_intent()
        alloc_candidates = []
        alloc, alloc_margin = self.allocator.allocate_usvs(
            {n: t for n, t in self.tracker.tracks.items()}, obs.usvs,
            self.usv_ctrl.targets, now, intent=self.intent, return_margin=True,
            candidates=alloc_candidates)
        self._prev_alloc_margin = alloc_margin

        # USV / UAV 动作（intent + mission 参数化）
        usv_acts = self.usv_ctrl.step(obs, self.tracker.tracks, legal, alloc, events,
                                      intent=self.intent, mission=self.mission)
        uav_acts = self.uav_mgr.step(obs, self.tracker, legal, events,
                                     intent=self.intent,
                                     threat_fn=lambda t, n: self.allocator.threat_score(t, n),
                                     coverage=self.coverage, mission=self.mission)
        self._emit_events(events)

        # 统计 + Commander 后台请求（快照摘要，绝不等待 LLM）
        self._record_stats(obs, events)
        self.resource = FriendlyResourceState.build(obs, self.usv_ctrl, self.uav_mgr,
                                                   self.tracker, self.coverage, now)
        clusters = self.cluster_builder.build(self.tracker.tracks, now)
        self.metrics["active_clusters_max"] = max(self.metrics["active_clusters_max"],
                                                  len(clusters))
        summary_text, valid_tracks, valid_clusters = self.summarizer.build_v5(
            obs, self.tracker, self.usv_ctrl, self.uav_mgr, self.intent,
            self.resource, clusters, self.coverage, self.mission, now)
        trigger = self._detect_trigger(obs, alloc_margin)
        state_sig = self._state_signature(obs)
        ctx = self._commander_ctx(obs)

        # 审计 B: fused state（tracks / resource / mission / clusters / coverage / sig / ctx）
        if rec is not None:
            rec.set_B(
                tracks={n: runtime_audit.serialize_track(t, now)
                        for n, t in self.tracker.tracks.items()},
                resource=runtime_audit.serialize_resource(self.resource),
                mission=self.mission,
                clusters=[runtime_audit.serialize_cluster(c) for c in clusters],
                coverage={"quality": round(self.coverage.coverage_quality(now), 3),
                          "cells_covered": sum(1 for c, lst in self.coverage.last_covered.items()
                                               if now - lst < COVERAGE_STALE),
                          "cells_total": len(self.coverage.last_covered) or self.coverage.nx * self.coverage.ny},
                state_signature=[list(x) if isinstance(x, tuple) else x for x in state_sig],
                commander_ctx=ctx,
                trigger=trigger,
                summary_hash=hash((summary_text,)),
            )
        # 审计 E: validated intent + allocator candidates/result/margin + controller result
        if rec is not None:
            rec.set_E(
                intent={"source": self.commander.get_source(),
                        **runtime_audit.record_intent(self.intent)},
                allocator={"result": alloc,
                           "margin": round(alloc_margin, 5) if alloc_margin is not None else None,
                           "candidates": alloc_candidates},
                controller={"usv_actions": [list(a) for a in usv_acts],
                            "uav_actions": [list(a) for a in uav_acts],
                            "usv_fsm": dict(self.usv_ctrl.state),
                            "uav_fsm": dict(self.uav_mgr.state)},
            )

        self.commander.maybe_request(obs.now, summary_text, valid_tracks, trigger,
                                     state_sig=state_sig, ctx=ctx,
                                     valid_clusters=valid_clusters,
                                     audit=self._audit,
                                     source_step_id=rec.step_id if rec is not None else None)
        self._prev_visible = obs.enemy_visible
        self._prev_usv_alive = obs.usv_alive
        self._ever_saw_enemy = self._ever_saw_enemy or obs.enemy_visible > 0
        if not self._ever_saw_ship and self.tracker.has_any_ship_track(obs.now):
            self._ever_saw_ship = True

        # 安全过滤
        requested = [list(a) for a in usv_acts + uav_acts]
        safe = self.safety.filter(usv_acts + uav_acts, obs, legal)
        if not safe:
            safe = [{"action_text": "空操作，等待一个宏观步 [noop]", "action_type": "noop"}]

        resp = self.client.apply(safe)

        # 审计 F: post-ActionSafety actions + exact /apply payload/response + next-step link
        if rec is not None:
            rec.set_F(
                requested_actions=requested,
                filtered_actions=safe,
                apply_payload={"actions": safe},
                apply_response=resp,
                feedback_link={"link_type": "audit_step_id",
                               "requested_step_id": rec.step_id,
                               "next_audit_step_id": rec.step_id + 1,
                               "response_sim_time": obs.now,
                               "response_wall_time": time.time()},
            )
            rec.finalize()

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
        n_air = sum(1 for v in uav_st.values() if v in (UAVManager.SEARCH, UAVManager.SCREEN, UAVManager.REACQUIRE, UAVManager.GLOBAL_SEARCH))
        n_rtb = sum(1 for v in uav_st.values() if v == UAVManager.RETURN)
        n_chg = sum(1 for v in uav_st.values() if v in (UAVManager.CHARGING, UAVManager.LANDING))
        n_loiter = sum(1 for v in uav_st.values() if v == UAVManager.SAFE_LOITER)
        tracks = self.tracker.tracks
        n_vis = sum(1 for t in tracks.values() if t.is_visible(obs.now))
        n_lost = len(tracks) - n_vis
        n_eng = sum(1 for t in tracks.values() if t.engaged)
        top = sorted(tracks.values(), key=lambda t: -self.allocator.threat_score(t, obs.now))[:3]
        top_s = " ".join(t.name + (f"(x{int(t.predicted_position(obs.now)[0]):,})"
                                   if t.has_position and t.predicted_position(obs.now) else "")
                         for t in top)
        print(f"[t={obs.now:,.0f}s] step={self.step} | MISSION={self.mission[:8]} | "
              f"USV: {obs.usv_alive}/{obs.usv_total} "
              f"(avail={n_avail} int={n_inter} lock={n_lock} frz={n_frz}) | "
              f"UAV: air={n_air} rtb={n_rtb} chg={n_chg} loiter={n_loiter} | "
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
        print("HYBRID AGENT V5 — Variable-Cardinality Hierarchical Maritime Agent")
        print(f"  启用UAV: {self.use_uavs} | LLM_ENABLED: {self.llm_enabled}")
        print("=" * 72)
        r = self.client.start()
        if not r or not r.get("成功"):
            print("启动失败(确认服务在运行)"); return
        print(f"对局 {r.get('对局编号')} 开始")
        self.prev_black_killed = 0
        run_id = f"ep{r.get('对局编号')}_{int(time.time())}"
        self._audit.set_run_id(run_id)

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
        self._dump_commander_audit()
        self._audit.flush_manifest()
        self.client.stop()
        print("Done")

    def _dump_commander_audit(self):
        """持久化 Commander 结构化审计（不含密钥/思维链）。"""
        try:
            import os as _os
            path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                                 "commander_audit_seed.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"episode": self.client and self.client.script_name,
                           "audit": self.commander.audit}, f, ensure_ascii=False, indent=1)
        except Exception:
            pass

    def _print_meta(self, sc, final_result=None):
        cs = self.commander.stats
        n = cs["calls"]
        avg = (cs["latency_sum"] / n) if n else 0.0
        result = final_result or self.stats["result"]
        m = self.metrics
        src = self.commander.get_source()
        print(f"[META] result={result} "
              f"victory_time={self.stats['victory_time']} "
              f"first_detection={self.stats['first_detection']} "
              f"first_lock={self.stats['first_lock']} "
              f"first_kill={m['first_kill_time']} "
              f"enemy_kills={sc.get('black_killed', 0)} "
              f"friendly_usv_losses={sc.get('white_ship_killed', 0)} "
              f"friendly_uav_losses={sc.get('white_uav_killed', 0)} "
              f"black_breakthrough={sc.get('black_breakthrough', 0)} "
              f"reacquire_attempts={m['reacquire_attempts']} "
              f"reacquire_success={m['reacquire_success']} "
              f"sensor_assisted_locks={m['sensor_assisted_locks']} "
              f"low_conf_commitments={m['low_conf_commitments']} "
              f"global_reacquire_entries={m['global_reacquire_entries']} "
              f"global_reacquire_success={m['global_reacquire_success']} "
              f"coverage_collapse_events={m['coverage_collapse_events']} "
              f"active_clusters_max={m['active_clusters_max']} "
              f"coverage_quality_final={self.coverage.coverage_quality(self.stats['victory_time'] or 0):.2f} "
              f"commander_source={src} "
              f"commander_calls={cs['calls']} commander_changes={cs['responses']} "
              f"commander_no_change={cs['no_change']} "
              f"commander_parse_failures={cs['parse_failures']} "
              f"commander_api_failures={cs['api_failures']} "
              f"commander_policy_failures={cs['policy_failures']} "
              f"commander_avg_latency={avg:.1f}")


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
