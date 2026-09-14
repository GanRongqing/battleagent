#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
agent_hybrid_v1.py — 白方通用海战 Agent V1（观测纯正、确定性、无 LLM）
=====================================================================

架构（单文件，六大组件）:
  AgentMain        主循环: status → obs(经/status结构化) → legal → track → threat → usv → uav → safety → apply → log
  TrackManager     敌情航迹管理（检测 / 常量速度外推 / 置信度衰减 / 丢弃）
  ThreatAllocator  威胁评估 + 2v1 / 3v1 目标分配（贪心）
  USVController    USV 控制器（宽前沿展开 / 拦截 / 锁定 / 锁定保持 / 分配保持）
  UAVManager       UAV 管理（搜索 / 重搜 / 返航 / 降落 / 充电 / 再起飞）
  ActionSafety     动作安全过滤（对 /legal_actions + 实时状态双重校验）

公平性铁律（最高优先级，勿违反）:
  # FAIR-PLAY RULE: 敌方运行时状态只能来自 HTTP 观测（/obs 语义文本 及 /status 中的
  #   观察信息.white_observation。雷达捕获条目含 name/position/velocity —— 这就是
  #   引擎 get_white_targets 的"共享感知"输出）。
  # 禁止读取: engine.black_* / get_state().black_* / 固定敌方初始坐标 / 固定敌方
  #   数量 / 固定敌方速度(如 vx=-10) / black_strategy / 直接连接仿真器内部 gRPC。
  # 敌方全部运动学（数量、位置、速度、航向）必须从观测在线推断，不做先验假设。

平台能力（源自 PLATFORM_CAPABILITIES.md，运行时已验证）:
  白 USV: max_speed=20 m/s, 雷达35km全向, 锁距<40km, 命中后冻结敌300s, 累计2命中击杀
  白 UAV : max_speed=150 m/s(电机) 但 /fly schema 上限 100 → 可执行上限 100 m/s,
          雷达60km±30°扇区(跟随航向), 电量=飞行时间线性消耗(total 25000s), 充电1.389/s
  共享感知: 任一红方探测目标 = 全局可见; 被锁/被冻结的蓝舰永久可见
  判定   : 蓝方全部USV死亡=胜利; 蓝舰突破x≤50000=失败; 我方(USV+UAV)全灭=失败

用法:
  python agent_hybrid_v1.py                     # 正常对局(启用UAV)
  python agent_hybrid_v1.py --no-uav            # USV-only 模式(UAV停在母舰)
  python agent_hybrid_v1.py --selftest          # TrackManager 单测(离线mock)
"""
import os
import sys
import json
import math
import time
import requests

# ════════════════════════════════════════════════════════════════
# 常量与全局参数
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
# 尸体检测: 被锁定的敌舰位置持续>600s不变 → 已击沉(尸体残留在intel)。
# 冻结最长300s(解冻后必移动), 因此>600s静止只可能是尸体。
CORPSE_AGE = 600.0

# UAV 电量安全
UAV_BATTERY_TOTAL = 25_000.0  # 总飞行时间(s), 与状态 battery 字段同单位
UAV_SAFETY_MARGIN = 300.0     # 返航余量(s), 任务要求"几百仿真秒"
UAV_RECHARGE_THRESHOLD = 0.80 # 再起飞电量阈值(80%)
UAV_RTB_RANGE_KM = 2_000.0    # 距回收舰 2km 内 → 发 land_uav(自动制导)
# 搜索巡逻东西界(世界东界 x=500000, 越过即死亡)。黑船自西(x=260000)来,
# 巡逻带覆盖战场前沿即可, 避免UAV一路向东飞出世界(第二局15架全灭主因)。
SEARCH_X_MIN = 140_000.0   # 巡逻西界: 到达后掉头向东
SEARCH_X_MAX = 260_000.0   # 巡逻东界: 到达后掉头向西

LOG_INTERVAL = 10          # 每 N 步打印聚合信息块


# ════════════════════════════════════════════════════════════════
# HTTP 客户端（复用/修复自 agent_llm.py / agent_defense.py 的稳定实现）
# ════════════════════════════════════════════════════════════════
def api(method, path, **kw):
    try:
        r = requests.request(method, f"{API}{path}", json=kw.get("json"), timeout=HTTP_TIMEOUT)
        if r.status_code == 200:
            ct = r.headers.get("content-type", "")
            return r.json() if "application/json" in ct else r.text
        return None
    except Exception as e:
        print(f"  [HTTP] {method} {path} 异常: {e}")
        return None


class ApiClient:
    """封装 5 个核心端点，返回结构化数据"""

    def start(self):
        return api("POST", "/start", json={"script_name": "测试用例1"})

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
# 观测解析 —— 只从 /status JSON 提取公平信息
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
    """/legal_actions 的解析 + 查询结构"""

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
# TrackManager —— 敌情航迹
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
            # 位置持续不变的敌舰 = 被冻结(≤300s)或已击沉(尸体在intel中永久可见)
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
    """维护所有已知敌舰航迹。

    规则:
      - 有观测速度则用观测速度; 丢失后用常量速度外推
      - 可见(30s内) 置信=1.0; 30-120s 估计=0.5; >180s 丢弃
      - 不引入卡尔曼等复杂滤波
    """

    def __init__(self):
        self.tracks = {}          # name -> EnemyTrack
        self.killed_names = set() # 已判定击沉的敌名(防止死灰复燃)

    def update(self, obs):
        """用 /status 的观测更新航迹。返回本步事件列表。"""
        now = obs.now
        events = []
        seen = set()

        # 1) 雷达捕获（主动情报）
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

        # 2) 被动告警（仅方位; 与雷达捕获同名的忽略）
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

        # 3) 未在本步出现的航迹: 外推 + 置信度衰减 + 丢弃
        #    0-30s 高置信; 30-120s 估计; 120-180s 维持估计; >180s 丢弃
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
        """用 USV 实时状态同步航迹的 engaged / assigned_usvs。

        is_locking + locking_unit 是引擎的真相来源（而非历史分配记录）。
        usv_targets（USVController.targets）补充正在拦截途中、尚未锁定的攻击者，
        使分配需求的统计与实际投入火力一致。
        """
        for t in self.tracks.values():
            t.assigned_usvs = set()
            t.engaged = False
        # 1) 引擎真实锁定状态
        for u in obs.usvs:
            if not u.get("is_alive"):
                continue
            lu = u.get("locking_unit")
            if lu and lu in self.tracks:
                self.tracks[lu].assigned_usvs.add(u["name"])
                self.tracks[lu].engaged = True
            elif lu:
                # 正在锁定一个已被丢弃/未知的敌 —— 保守地建一个空航迹
                if lu not in self.tracks and lu not in self.killed_names:
                    t = EnemyTrack(lu, obs.now)
                    t.confidence = 0.5
                    self.tracks[lu] = t
        # 2) 拦截途中（已分配未锁定）的攻击者
        if usv_targets:
            for uname, tname in usv_targets.items():
                if not tname or tname not in self.tracks:
                    continue
                if uname in self.tracks[tname].assigned_usvs:
                    continue
                self.tracks[tname].assigned_usvs.add(uname)

    def kill_detect(self, obs, prev_black_killed):
        """根据奖励计数 black_killed 判定击沉，返回 (事件列表, 被击沉名列表)。

        两个证据源:
          A) 曾被我方锁定、如今从情报中消失的敌(锁定/冻结永久可见, 消失=已沉)
          B) 尸体检测: 引擎在击沉后不会复位 locker.locked,
             尸体因此永远残留在白方 intel 中(位置固定不动)。
             被我方锁定且位置持续>CORPSE_AGE(600s)不变的敌 = 已击沉。
             冻结最长300s(解冻必移动), 故>600s静止只可能是尸体。
        """
        killed = []
        now = obs.now
        delta = obs.black_killed - prev_black_killed
        # 证据A: engaged 且从 intel 消失
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
        # 证据B: 尸体检测(与计数/engaged无关, 逐步清扫)。
        # 静止>600s必为尸体: 冻结最长300s(解冻必移动), 2次命中即击沉;
        # 白方观测的position是引擎实时坐标, 不会因情报粘滞而假静止。
        # 不依赖 engaged —— 因为 is_locking 在观测快照中周期性翻转。
        for name, t in self.tracks.items():
            if name in killed or not t.has_position:
                continue
            if t.stationary_duration(now) >= CORPSE_AGE:
                killed.append(name)
        # 去重并落账
        for name in dict.fromkeys(killed):
            self.killed_names.add(name)
            del self.tracks[name]
        return [("KILL", name) for name in dict.fromkeys(killed)], list(dict.fromkeys(killed))

    def lost_high_threat(self, now, max_age=EST_CONF_AGE):
        """返回丢失但高威胁、值得UAV重搜的航迹（有位置、需有估计置信）。"""
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
# ThreatAllocator —— 威胁评估 + 2v1/3v1 贪心分配
# ════════════════════════════════════════════════════════════════
class ThreatAllocator:
    """对每个航迹计算威胁分，按威胁从高到低贪心分配可用的 USV。

    威胁分（全部来自观测，速度取自航迹观测速度，不假设 vx=-10）:
      高威胁条件: 距突破线近 / 有向西危险速度 / 高置信 / 尚无攻击者
    分配: 常规 2v1; 接近突破线(EMERGENCY_3V1_X 以西)且有2攻击者 → 3v1
    """

    def threat_score(self, t, now):
        pos = t.predicted_position(now)
        if pos is None:
            return 0.0
        x = pos[0]
        # 距突破线: 越近威胁越高
        d_break = max(0.0, x - BREAKTHROUGH_X)
        prox = max(0.0, min(1.0, 1.0 - d_break / 200_000.0))
        # 向西速度(vx<0) → 威胁高。绝不假设固定速度，只用观测值
        vx = t.last_velocity[0] if t.last_velocity else 0.0
        vel = max(0.0, min(1.0, -vx / 20.0))
        # 置信度
        conf = t.confidence
        # 已分配攻击者越少越优先补足
        alloc = max(0.0, (2.0 - len(t.assigned_usvs)) / 2.0)
        score = 1.4 * prox + 0.8 * vel + 1.0 * conf + 0.8 * alloc
        # 已在交战的稍加权重(优先打满/补刀)，但不压倒更近的新威胁
        if t.engaged:
            score += 0.2
        return score

    @staticmethod
    def _is_ship(name):
        # 胜利与突破只由敌舰决定；敌UAV是侦察机，击杀敌舰即可获胜。
        # 名称来自观测（/obs），仅为公共规则知识，非敌方运行时真相。
        return "usv" in name

    def allocate_usvs(self, tracks, usvs, usv_map, now):
        """需要USV位置时使用本函数(简单版, 直接用距离)。

        只分配 USV 去锁定敌舰（黑_usv*）；敌 UAV 不分配火力（不产生突破、
        且击杀敌舰即获胜）。第一局证明追逐UAV浪费约2000s且无所获。
        """
        usv_pos = {u["name"]: (u["position"][0], u["position"][1])
                   for u in usvs if u.get("is_alive") and u.get("position")}
        available = [name for name, trg in usv_map.items()
                     if trg is None and name in usv_pos]
        scored = []
        for name, t in tracks.items():
            if not t.has_position or name in _KILLED:
                continue
            if not self._is_ship(name):
                continue
            cur = len(t.assigned_usvs)
            pos = t.predicted_position(now)
            want = 0
            if cur < 2:
                want = 2 - cur
            elif cur < 3 and pos is not None and pos[0] < EMERGENCY_3V1_X:
                want = 1
            if want > 0:
                scored.append((self.threat_score(t, now), name, want, pos))
        scored.sort(key=lambda x: -x[0])
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
# USVController —— USV 状态机 + 锁定逻辑
# ════════════════════════════════════════════════════════════════
class USVController:
    """USV 状态: DEAD / FROZEN / LOCKING / INTERCEPTING / AVAILABLE

    铁律:
      - 分配保持: 已锁定目标绝不切换; 拦截中目标未失效也绝不切换
      - 锁定后保持 <40km(继续朝目标机动)
      - 被敌锁定不后撤(后撤=放弃我方锁定进度, 送死)
    """

    # 状态名
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

            # ---- LOCKING: 硬保持, 绝不切换 ----
            if st == self.LOCKING:
                trg = u.get("locking_unit")
                new_targets[name] = trg
                # 保持 <40km: 持续朝目标机动
                if trg in tracks and tracks[trg].has_position:
                    tpos = tracks[trg].predicted_position(obs.now)
                    if tpos is not None and pos is not None:
                        actions.append(self._move(name, pos, tpos))
                continue

            # ---- FROZEN: 不能动不能锁 ----
            if st == self.FROZEN:
                new_targets[name] = self.targets.get(name)
                continue

            # ---- AVAILABLE / INTERCEPTING ----
            cur = self.targets.get(name)
            # 当前目标失效? (被丢弃 / 被击沉 / 消失)
            if cur is not None:
                t = tracks.get(cur)
                if t is None or not t.has_position or cur in _KILLED:
                    events.append(("RELEASE", f"{name}->{cur}(目标失效)"))
                    cur = None

            # 机会锁定(P0-3 关键修复): 若锁距内存在可锁定的敌舰, 立即锁定最近、
            # 攻击者最少的那个 —— 绝不让USV越过可锁定敌舰去追远处的分配目标。
            # 第一局败因正是: 仅5-6艘USV在交战窗口内实际开锁, 其余在赶路。
            opp = self._opportunistic_lock(name, pos, tracks, legal, obs)
            if opp is not None:
                if opp != self.targets.get(name):
                    events.append(("ASSIGN", f"{name}->{opp}(机会锁定)"))
                new_targets[name] = opp
                actions.append((f"{name} 锁定 {opp}", "lock"))
                continue

            # 无目标 → 采纳分配器建议（本步已释放/从未分配过目标）
            if cur is None:
                for trk, usvs in alloc_result.items():
                    if name in usvs:
                        cur = trk
                        events.append(("ASSIGN", f"{name}->{trk}"))
                        break
            new_targets[name] = cur

            if cur is None:
                # AVAILABLE: 东向宽前沿
                actions.append(self._move(name, pos, (pos[0] + 100_000, pos[1]) if pos else None))
                continue

            # INTERCEPTING
            t = tracks.get(cur)
            if t is None or not t.has_position:
                new_targets[name] = None
                actions.append(self._move(name, pos, (pos[0] + 100_000, pos[1]) if pos else None))
                continue
            tpos = t.predicted_position(obs.now)
            if pos is None or tpos is None:
                continue
            dist = math.hypot(tpos[0] - pos[0], tpos[1] - pos[1])

            # 锁距内且合法 → 锁定
            if dist < LOCK_RANGE and legal.can_lock(name, cur):
                actions.append((f"{name} 锁定 {cur}", "lock"))
                # 事件: 成功与否由 API 结果确认, 这里只发指令
            else:
                actions.append(self._move(name, pos, tpos))

        self.targets = new_targets
        return actions

    def _opportunistic_lock(self, name, pos, tracks, legal, obs):
        """锁距(<40km)内选择最近、攻击者最少的可锁定敌舰。"""
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
            # 键: 攻击者越少越优先(先铺开1v1覆盖), 其次距离越近越优先
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
# UAVManager —— UAV 状态机 + 电量安全
# ════════════════════════════════════════════════════════════════
class UAVManager:
    """UAV 状态: ON_SHIP / SEARCH / REACQUIRE / RETURN / LANDING / CHARGING

    电量安全(核心):
      estimated_return_time = 到最近空机库存活USV距离 / 可执行速度(UAV_FLY_SPEED=100)
      若 battery_remaining < estimated_return_time + SAFETY_MARGIN → 立即返航
    回收舰选择: 最近且空机库(非母舰也可)的存活USV
    再起飞: 电量 > 80% 且存在搜索/重搜需求
    """

    ON_SHIP, SEARCH, REACQUIRE, RETURN, LANDING, CHARGING = \
        "ON_SHIP", "SEARCH", "REACQUIRE", "RETURN", "LANDING", "CHARGING"

    def __init__(self, enabled=True):
        self.enabled = enabled
        self.state = {}
        self.reacquire_lock = {}   # track_name -> uav_name (每丢失高威胁航迹最多1架)
        self.search_dir = {}       # uav_name -> +1(向东) / -1(向西) 巡逻方向

    def step(self, obs, tracker, legal, events):
        if not self.enabled:
            return []
        tracks = tracker.tracks
        actions = []
        # 收集存活USV位置与机库占用
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
        # 已分配重搜的航迹不再重复分配
        for trk in lost:
            if trk.name in self.reacquire_lock:
                uavn = self.reacquire_lock[trk.name]
                if not any(uv.get("name") == uavn and uv.get("is_alive") and not uv.get("is_at_usv") for uv in obs.uavs):
                    del self.reacquire_lock[trk.name]

        for u in obs.uavs:
            if not u.get("is_alive"):
                self.state[u["name"]] = None
                continue
            name = u["name"]
            batt = u.get("battery", UAV_BATTERY_TOTAL)
            at_usv = u.get("is_at_usv", True)
            pos = (u["position"][0], u["position"][1]) if u.get("position") else None
            st = self.state.get(name)

            # 找回收舰: 最近空机库存活USV（空机库 = 该舰未停靠其它UAV）
            recovery = None
            recv_d = float("inf")
            if pos is not None:
                for ui in usv_info:
                    has_other = any(d != name for d in ui["dock"])
                    if has_other:
                        continue  # 机库被别的UAV占用
                    d = math.hypot(ui["pos"][0] - pos[0], ui["pos"][1] - pos[1]) if ui["pos"] else float("inf")
                    if d < recv_d:
                        recv_d, recovery = d, ui["name"]

            # ---- 在母舰上 (充电中) ----
            if at_usv:
                if st in (None, self.ON_SHIP, self.CHARGING):
                    self.state[name] = self.CHARGING
                # 电量足够 + 有需求 → 再起飞
                need_search = len(lost) > 0 or obs.enemy_visible == 0
                if batt >= UAV_BATTERY_TOTAL * UAV_RECHARGE_THRESHOLD and need_search:
                    home = u.get("home_name")
                    if legal.can_launch(name, home):
                        # 若为重搜航迹分配则定向, 否则扇面搜索
                        actions.append(self._launch(name, home))
                        events.append(("UAV RELAUNCH", name))
                        self.state[name] = self.SEARCH
                continue

            # ---- 飞行中 ----
            if pos is None:
                continue
            est_ret = recv_d / UAV_FLY_SPEED if recovery else float("inf")
            # 电量安全: 电量不足以返航 → 立即返航
            if batt < est_ret + UAV_SAFETY_MARGIN:
                if st != self.RETURN:
                    events.append(("UAV RTB", f"{name}(电量{batt:.0f}<{est_ret:.0f}+{UAV_SAFETY_MARGIN:.0f})"))
                self.state[name] = self.RETURN

            st = self.state.get(name, self.SEARCH)

            # REACQUIRE: 有丢失高威胁航迹未分配
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
                        actions.append(self._search_fly(name, pos))

            # RETURN / LANDING
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

    def _search_fly(self, name, pos):
        # 巡逻搜索: 在 SEARCH_X_MIN..SEARCH_X_MAX 之间东西往复, 防止飞出世界东界。
        # 到界掉头; 未到界按自身y索引扇面航向(东偏)覆盖宽扇区。
        d = self.search_dir.get(name, 1)
        if pos is not None:
            if pos[0] >= SEARCH_X_MAX:
                d = -1
            elif pos[0] <= SEARCH_X_MIN:
                d = 1
        self.search_dir[name] = d
        idx = int(name.replace("white_uav", "")) if "white_uav" in name else 0
        if d > 0:
            crs = 90.0 + (idx - 8) * 7.0   # 向东扇面: -56° .. +49° 围绕正东
        else:
            crs = 270.0 + (idx - 8) * 7.0  # 向西扇面: 244° .. 329° 围绕正西
        crs = crs % 360.0
        return (f"{name} 飞行 target_speed={UAV_FLY_SPEED:.1f} target_course={crs:.1f}", "fly")


# ════════════════════════════════════════════════════════════════
# ActionSafety —— 动作安全过滤
# ════════════════════════════════════════════════════════════════
class ActionSafety:
    """对候选动作双重校验(legal_actions + 实时状态), 杜绝 400 批量失败。

    规则:
      - 每单位每步只允许一个动作(后发覆盖)
      - 死亡的USV/UAV不动作
      - 冻结USV不移动/不锁定
      - 目标不在雷达捕获中的不锁定(非法列表过滤)
      - 已锁定目标不重复锁定
      - 不在机库不 launch; 机库满不 land
      - fly 与 land_uav 同一步互斥
    """

    def __init__(self):
        pass

    def filter(self, actions, obs, legal):
        """actions: [(action_text, action_type)] → 返回安全列表[{action_text,action_type}]"""
        # 实时状态索引
        usv_state = {u["name"]: u for u in obs.usvs}
        uav_state = {u["name"]: u for u in obs.uavs}
        seen_unit = set()
        out = []
        for text, atype in actions:
            unit = self._unit_of(text)
            if unit is None:
                continue
            if unit in seen_unit:
                continue  # 同一步同单位只保留第一个
            # 存活与状态检查
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
                        continue  # 已锁别艘, 引擎禁止换锁
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
# AgentMain —— 主循环
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

    # ── 事件聚合 ──
    def _emit_events(self, evs):
        for tag, detail in evs:
            print(f"      [{tag}] {detail}")

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

        # 威胁分配(使用 USV 位置)
        alloc = self.allocator.allocate_usvs(
            {n: t for n, t in self.tracker.tracks.items()}, obs.usvs,
            self.usv_ctrl.targets, now)

        # USV / UAV 动作
        usv_acts = self.usv_ctrl.step(obs, self.tracker.tracks, legal, alloc, events)
        uav_acts = self.uav_mgr.step(obs, self.tracker, legal, events)
        self._emit_events(events)

        # 安全过滤
        safe = self.safety.filter(usv_acts + uav_acts, obs, legal)
        if not safe:
            safe = [{"action_text": "空操作，等待一个宏观步 [noop]", "action_type": "noop"}]

        resp = self.client.apply(safe)
        # 若 apply 返回 None(HTTP失败), 打印但继续

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
        top = sorted(tracks.values(), key=lambda t: -self.allocator.threat_score(t, obs.now))[:3]
        top_s = " ".join(f"{t.name}(x{int(t.predicted_position(obs.now)[0]):,})" if t.has_position and t.predicted_position(obs.now) else t.name
                         for t in top)
        print(f"[t={obs.now:,.0f}s] step={self.step} | USV: {obs.usv_alive}/{obs.usv_total} "
              f"(avail={n_avail} int={n_inter} lock={n_lock} frz={n_frz}) | "
              f"UAV: air={n_air} rtb={n_rtb} chg={n_chg} | "
              f"TRACKS: vis={n_vis} lost={n_lost} | TOP: {top_s} | "
              f"KILL={obs.black_killed} | ACTIONS={len(safe)}")

    def run(self):
        print("=" * 72)
        print("HYBRID AGENT V1 — 观测纯正确定性Agent")
        print(f"  启用UAV: {self.use_uavs}")
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
            # 引擎连续推进, 决策循环需足够快, 不需要额外 sleep 大延迟
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
        self.client.stop()
        print("Done")


# ════════════════════════════════════════════════════════════════
# TrackManager 单测（离线 mock）
# ════════════════════════════════════════════════════════════════
def selftest_trackmanager():
    print("=== TrackManager 单测 ===")
    import tempfile
    class FakeObs:
        def __init__(self, now, active=(), passive=()):
            self.now = now
            self.active = [{"name": n, "position": p, "velocity": v} for n, p, v in active]
            self.passive = [{"name": n, "bearing": b} for n, b in passive]
            self.usvs = []
            self.black_killed = 0

    tm = TrackManager()
    # 1) 检测
    ev = tm.update(FakeObs(0.0, [("b1", (250000, 300000), (-10, 0))]))
    assert any(e[0] == "DETECT" and e[1] == "b1" for e in ev), "未检测到新目标"
    t = tm.tracks["b1"]
    assert t.has_position and t.last_velocity == (-10, 0) and t.is_visible(0.0)
    print("  [1] 检测 ✓")

    # 2) 预测: 60s后 → 位置左移 600m
    ev = tm.update(FakeObs(60.0, []))   # 丢失
    pp = tm.tracks["b1"].predicted_position(60.0)
    assert pp == (249400, 300000), f"预测错误 {pp}"
    assert tm.tracks["b1"].confidence == 0.5, "60s应降为估计置信"
    print("  [2] 常量速度外推 + 置信衰减 ✓")

    # 3) 重见: 恢复高置信
    tm.update(FakeObs(65.0, [("b1", (249350, 300000), (-10, 0))]))
    assert tm.tracks["b1"].confidence == 1.0 and tm.tracks["b1"].is_visible(65.0)
    print("  [3] 重新探测恢复 ✓")

    # 4) 过期丢弃: 190s未见 → 删除
    tm.update(FakeObs(255.0, []))   # last_seen=65, 190s后
    assert "b1" not in tm.tracks, "190s后应丢弃"
    print("  [4] 过期丢弃 ✓")

    # 5) 被动告警(仅方位)
    tm2 = TrackManager()
    tm2.update(FakeObs(0.0, [], [("b2", 120.0)]))
    assert "b2" in tm2.tracks and not tm2.tracks["b2"].has_position
    assert tm2.tracks["b2"].bearing == 120.0
    print("  [5] 被动告警 ✓")

    # 6) kill_detect: 曾锁定目标从情报消失 + black_killed 增加 → 判定击沉
    tm3 = TrackManager()
    tm3.update(FakeObs(0.0, [("b3", (240000, 300000), (-10, 0))]))
    tm3.tracks["b3"].engaged = True
    tm3.tracks["b3"].assigned_usvs = {"white_usv1", "white_usv2"}
    evs, killed = tm3.kill_detect(FakeObs(100.0), prev_black_killed=0)
    assert killed == [], "应无击沉(black_killed未增加)"
    evs, killed = tm3.kill_detect(FakeObs(100.0, active=[]), prev_black_killed=0)
    # black_killed 仍为0 → 不判定
    assert killed == []
    evs, killed = tm3.kill_detect(FakeObs(100.0, active=[]), prev_black_killed=0)
    # 构造 black_killed 增加
    fo = FakeObs(100.0, active=[])
    fo.black_killed = 1
    evs, killed = tm3.kill_detect(fo, prev_black_killed=0)
    assert killed == ["b3"], f"应判定击沉b3, got {killed}"
    assert "b3" in tm3.killed_names and "b3" not in tm3.tracks
    print("  [6] 击沉判定 ✓")

    # 7) 尸体检测: 被锁定 + 位置持续>600s不变 → 判定击沉(尸体残留在intel)
    tm4 = TrackManager()
    # t=0 探测, 位置此后不再变化(尸体)
    tm4.update(FakeObs(0.0, [("b4", (200000, 300000), (-10, 0))]))
    tm4.tracks["b4"].engaged = True
    tm4.tracks["b4"].assigned_usvs = {"white_usv1"}
    # 后续逐步更新: 位置固定不动(尸体在intel中位置不变)
    for t in (100.0, 200.0, 400.0, 620.0):
        tm4.update(FakeObs(t, [("b4", (200000, 300000), (-10, 0))]))
        tm4.tracks["b4"].engaged = True   # 我方USV仍锁定着这具尸体
    evs, killed = tm4.kill_detect(FakeObs(650.0, active=[("b4", (200000, 300000), (-10, 0))]), prev_black_killed=1)
    assert killed == ["b4"], f"静止>600s应判定尸体击沉, got {killed}"
    assert "b4" not in tm4.tracks and "b4" in tm4.killed_names
    print("  [7] 尸体检测(静止>600s) ✓")

    print("=== TrackManager 全部通过 ===")
    return True


# ════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    use_uavs = True
    selftest = False
    for a in sys.argv[1:]:
        if a == "--no-uav":
            use_uavs = False
        if a == "--selftest":
            selftest = True
    if selftest:
        ok = selftest_trackmanager()
        sys.exit(0 if ok else 1)
    AgentMain(use_uavs=use_uavs).run()
