# -*- coding: utf-8 -*-
"""maritime_metrics.py — evaluator-side 统计 instrumentation（accounting only，不影响 Agent）

本模块在评估进程中以独立轮询线程读取 /status，统计：
  - 我方单位死亡（death_time / death_cause）
  - 敌方四类终局（combat_killed / out_of_bounds / breakthrough / survived）
  - 我方探索面积（USV 360° / UAV 前向 ±30°，固定网格）
  - 每单位探索面积（含 first-coverage 归因）
  - 每 USV damage_hits / kill_credit（基于可观测锁链事件，属推断，报告中注明）
"""

import math
import time
import threading
import json

API = "http://127.0.0.1:8000"
USV_RADAR = 35_000.0
UAV_RADAR = 60_000.0
UAV_HALF_FOV = 30.0
USV_COMBAT_MAX = 40_000.0

# 战场合法区域（任务区域.json 八边形近似，用于 OOB 判定）
AREA_X0, AREA_X1 = -500.0, 300_500.0
AREA_Y0, AREA_Y1 = -500.0, 673_500.0
BREAK_X = 50_000.0


def bearing_to(frm, to):
    dx = to[0] - frm[0]
    dy = to[1] - frm[1]
    return math.degrees(math.atan2(dx, dy)) % 360.0


def parse_sim_time(hm):
    try:
        hh, mm, ss = [int(x) for x in str(hm).split(":")]
        return hh * 3600 + mm * 60 + ss
    except Exception:
        return 0.0


def polygon_area(points):
    """shoelace，points = [(x,y),...]"""
    n = len(points)
    a = 0.0
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


# 任务区域多边形面积（用于 exploration_ratio 分母）
def load_battlefield_area_km2():
    try:
        import os
        p = "/root/autodl-tmp/hsystem/hsystem/sim_script/20250819TZB/Demo/任务区域.json"
        pts = json.load(open(p))
        area_m2 = polygon_area([tuple(v) for v in pts.values()])
        return area_m2 / 1e6
    except Exception:
        return 540.0  # 兜底：~[0,300]km × [0,180]km 量级


class ExplorationCoverageTracker:
    """测量用 coverage（与 Agent decision CoverageMap 完全分开）。

    固定网格（5km cell），所有场景相同，不随舰队数量改变。
    USV footprint = 360° 35km 圆；UAV footprint = 前向 ±30° 60km 锥。
    """

    CELL = 5000.0

    def __init__(self):
        self.X0, self.X1 = 0.0, 300_000.0
        self.Y0, self.Y1 = 80_000.0, 620_000.0
        self.nx = max(1, int((self.X1 - self.X0) / self.CELL))
        self.ny = max(1, int((self.Y1 - self.Y0) / self.CELL))
        self.cell_centers = {}
        for ix in range(self.nx):
            x = self.X0 + (ix + 0.5) * self.CELL
            for iy in range(self.ny):
                y = self.Y0 + (iy + 0.5) * self.CELL
                self.cell_centers[(ix, iy)] = (x, y)
        self.covered = {}          # (ix,iy) -> first_time
        self.first_unit = {}       # (ix,iy) -> unit
        self.unit_cells = {}       # unit -> set((ix,iy))
        self.cell_area_km2 = (self.CELL / 1000.0) ** 2

    def _cells_in_circle(self, cx, cy, radius):
        i0 = max(0, int((cx - radius - self.X0) / self.CELL))
        i1 = min(self.nx - 1, int((cx + radius - self.X0) / self.CELL))
        j0 = max(0, int((cy - radius - self.Y0) / self.CELL))
        j1 = min(self.ny - 1, int((cy + radius - self.Y0) / self.CELL))
        r2 = radius * radius
        for ix in range(i0, i1 + 1):
            x, _ = self.cell_centers[(ix, j0)]
            for iy in range(j0, j1 + 1):
                _, y = self.cell_centers[(ix, iy)]
                dx = x - cx
                dy = y - cy
                if dx * dx + dy * dy <= r2:
                    yield (ix, iy)

    def _cells_in_cone(self, cx, cy, heading, radius, half=UAV_HALF_FOV):
        for (ix, iy) in self._cells_in_circle(cx, cy, radius):
            x, y = self.cell_centers[(ix, iy)]
            ang = bearing_to((cx, cy), (x, y))
            diff = abs((ang - heading + 180.0) % 360.0 - 180.0)
            if diff <= half:
                yield (ix, iy)

    def mark(self, unit, x, y, heading, radius, cone, t):
        cells = self._cells_in_circle(x, y, radius) if cone is None \
            else self._cells_in_cone(x, y, heading, radius, cone)
        uc = self.unit_cells.setdefault(unit, set())
        for c in cells:
            if c not in self.covered:
                self.covered[c] = t
                self.first_unit[c] = unit
            uc.add(c)

    def unit_explored_km2(self, unit):
        return len(self.unit_cells.get(unit, ())) * self.cell_area_km2

    def total_explored_km2(self):
        return len(self.covered) * self.cell_area_km2

    def exploration_ratio(self, valid_area_km2):
        return self.total_explored_km2() / valid_area_km2 if valid_area_km2 else 0.0

    def first_coverage_km2(self, unit):
        return sum(1 for u in self.first_unit.values() if u == unit) * self.cell_area_km2


class GameMetricsCollector:
    """单局度量收集（独立轮询线程读取 /status，不修改 Agent）。"""

    def __init__(self, api=API, poll_interval=3.0, valid_area_km2=None):
        self.api = api
        self.poll_interval = poll_interval
        self.valid_area_km2 = valid_area_km2 if valid_area_km2 else load_battlefield_area_km2()
        self.explorer = ExplorationCoverageTracker()
        self._stop = False
        self.samples = []
        self.reward = {}            # 最新累计奖励
        self.prev_reward = {}
        self.friendly = {}          # name -> {type, alive, death_time, death_cause, last_pos, last_heading, out_of_bounds}
        self.enemy = {}             # name -> {last_pos, reached_break, out_of_bounds, engaged_by(set), disappeared, first_seen, last_seen}
        self.usv_chain = {}         # usv -> {target, start}
        self.prev_locking = {}      # usv -> target
        self.hit_credit = {}        # usv -> hits（基于锁链释放事件推断）
        self.kill_credit = {}       # usv -> kills（基于消失敌舰+last locker 推断）
        self.usv_targets = {}       # usv -> set(target)
        self.last_locker = {}       # enemy -> usv（最近锁定者）
        self.thread = None
        self.start_wall = None

    # ── 轮询 ──
    def start(self):
        self.start_wall = time.time()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self):
        self._stop = True
        if self.thread:
            self.thread.join(timeout=5)

    def _loop(self):
        import requests
        while not self._stop:
            try:
                r = requests.get(f"{self.api}/status", timeout=5)
                if r.status_code == 200:
                    st = r.json()
                    if isinstance(st, dict) and st.get("资源快照"):
                        self.observe(st)
                    if st.get("已结束"):
                        break
            except Exception:
                pass
            time.sleep(self.poll_interval)

    # ── 单次观测 ──
    def observe(self, st):
        now = parse_sim_time(st.get("局内时间", "00:00:00"))
        self.reward = st.get("奖励信号", {}) or {}
        snap = st.get("资源快照", {}) or {}
        units = snap.get("单位状态", {}) or {}
        intel = snap.get("观察信息", {}) or {}
        active = intel.get("white_observation", {}) or {}

        usvs = units.get("white_usv_states", []) or []
        uavs = units.get("white_uav_states", []) or []
        enemies = active.get("雷达捕获", []) or []

        # 奖励增量
        def d(key):
            p = self.prev_reward.get(key, 0)
            c = self.reward.get(key, 0)
            return max(0, c - p)
        hit_delta = d("black_hit")
        kill_delta = d("black_killed")
        wusv_delta = d("white_ship_killed")
        wuav_delta = d("white_uav_killed")
        self.prev_reward = dict(self.reward)

        # 我方 USV
        for u in usvs:
            name = u.get("name")
            if not name:
                continue
            alive = u.get("is_alive", False)
            pos = tuple(u.get("position", [None, None])[:2]) if u.get("position") else None
            f = self.friendly.setdefault(name, {"type": "USV", "alive": True,
                                                "death_time": None, "death_cause": None,
                                                "last_pos": None, "last_heading": None,
                                                "out_of_bounds": False})
            if alive:
                f["last_pos"] = pos
                if pos:
                    if not (AREA_X0 <= pos[0] <= AREA_X1 and AREA_Y0 <= pos[1] <= AREA_Y1):
                        f["out_of_bounds"] = True
            elif f["alive"]:
                f["alive"] = False
                f["death_time"] = now
                f["death_cause"] = self._usv_cause(u, f, now)
            # 锁链跟踪（damage/kill 归因）
            locking = u.get("is_locking") and u.get("locking_unit")
            if locking:
                tgt = u["locking_unit"]
                self.usv_targets.setdefault(name, set()).add(tgt)
                self.last_locker[tgt] = name
                if name not in self.usv_chain:
                    self.usv_chain[name] = {"target": tgt, "start": now}
                if tgt in self.enemy:
                    self.enemy[tgt]["engaged_by"].add(name)
            # 本步释放的链（300s 窗口结束）
            released = []
            prev = self.prev_locking.get(name)
            if prev and not locking:
                released.append(name)
            if locking:
                self.prev_locking[name] = tgt
            else:
                self.prev_locking.pop(name, None)
            if hit_delta > 0 and released:
                for u2 in released[:hit_delta]:
                    self.hit_credit[u2] = self.hit_credit.get(u2, 0) + 1
                hit_delta -= len(released[:hit_delta])
        # hit 归因兜底：释放数不足时给仍在锁链的 USV
        if hit_delta > 0:
            for uname in list(self.usv_chain.keys())[:hit_delta]:
                self.hit_credit[uname] = self.hit_credit.get(uname, 0) + 1

        # 我方 UAV（探索）
        for u in uavs:
            name = u.get("name")
            if not name:
                continue
            alive = u.get("is_alive", False)
            pos = tuple(u.get("position", [None, None])[:2]) if u.get("position") else None
            at_usv = u.get("is_at_usv", True)
            f = self.friendly.setdefault(name, {"type": "UAV", "alive": True,
                                                "death_time": None, "death_cause": None,
                                                "last_pos": None, "last_heading": None,
                                                "out_of_bounds": False})
            if alive:
                f["last_pos"] = pos
                if pos:
                    if not (AREA_X0 <= pos[0] <= AREA_X1 and AREA_Y0 <= pos[1] <= AREA_Y1):
                        f["out_of_bounds"] = True
            elif f["alive"]:
                f["alive"] = False
                f["death_time"] = now
                f["death_cause"] = self._uav_cause(u, f, now)
            # 探索（空中 UAV 用前向锥）
            if alive and pos and not at_usv:
                hdg = float(u.get("course", 0) or 0)
                self.explorer.mark(name, pos[0], pos[1], hdg, UAV_RADAR, UAV_HALF_FOV, now)

        # 我方 USV 探索（360°）
        for u in usvs:
            name = u.get("name")
            if not name:
                continue
            if u.get("is_alive") and u.get("position"):
                p2 = u["position"][:2]
                self.explorer.mark(name, p2[0], p2[1], 0.0, USV_RADAR, None, now)

        # 敌方
        active_names = set()
        for e in enemies:
            name = e.get("name")
            if not name:
                continue
            active_names.add(name)
            pos = tuple(e.get("position", [None, None])[:2]) if e.get("position") else None
            en = self.enemy.setdefault(name, {"last_pos": None, "reached_break": False,
                                              "out_of_bounds": False, "engaged_by": set(),
                                              "disappeared": False, "first_seen": now,
                                              "last_seen": now, "oob_time": None,
                                              "oob_pos": None})
            if pos:
                en["last_pos"] = pos
                en["last_seen"] = now
                if pos[0] <= BREAK_X:
                    en["reached_break"] = True
                if not (AREA_X0 <= pos[0] <= AREA_X1 and AREA_Y0 <= pos[1] <= AREA_Y1):
                    if not en["out_of_bounds"]:
                        en["out_of_bounds"] = True
                        en["oob_time"] = now
                        en["oob_pos"] = pos
        # 消失敌舰（本步从 active 消失）
        for name, en in list(self.enemy.items()):
            if name not in active_names and not en["disappeared"]:
                en["disappeared"] = True
                en["disappear_time"] = now

        self.samples.append((now, len(usvs), len(uavs)))

    def _usv_cause(self, u, f, now):
        # 被冻结/被锁（combat）或出界；否则 unknown
        if f.get("out_of_bounds"):
            return "out_of_bounds"
        if u.get("is_locked") or u.get("is_frozen"):
            return "combat"
        return "unknown"

    def _uav_cause(self, u, f, now):
        if f.get("out_of_bounds"):
            return "out_of_bounds"
        b = u.get("battery")
        if b is not None and b <= 0:
            return "battery"
        return "unknown"

    # ── 终局分类（reward-driven：black_killed 统计所有黑 USV 死亡，含 combat/OOB/突破 judge kill）──
    def finalize(self, bu=0, agent_kill_names=None):
        black_killed = int(self.reward.get("black_killed", 0) or 0)
        brk_reward = int(self.reward.get("black_breakthrough", 0) or 0)
        # 观测到的突破/出界 USV 名单（用于识别）
        known_usv = [n for n, en in self.enemy.items() if "usv" in n]
        brk_names = [n for n in known_usv if self.enemy[n]["reached_break"]]
        oob_names = [n for n in known_usv
                     if self.enemy[n]["out_of_bounds"] and not self.enemy[n]["reached_break"]]
        # 事件计数（reward 权威）
        brk_count = max(brk_reward, len(brk_names))
        oob_count = len(oob_names)
        # combat killed = 总黑USV死亡 - 突破 - 出界（其余全为白方战斗击杀）
        combat_count = max(0, black_killed - brk_count - oob_count)
        survived = max(0, bu - black_killed)
        unknown = max(0, bu - combat_count - oob_count - brk_count - survived)
        # kill credit：对非突破/非出界的、被白方锁定过的黑 USV 计击杀给 last locker
        kill_credit = {}
        credited = 0
        for n in known_usv:
            if n in brk_names or n in oob_names:
                continue
            if n not in self.last_locker:
                continue
            kill_credit[self.last_locker[n]] = kill_credit.get(self.last_locker[n], 0) + 1
            credited += 1
        # 若 credited > combat_count（个别锁链在外时判死），截断；否则差量不补（推断局限）
        if credited > combat_count:
            over = credited - combat_count
            for locker in list(kill_credit.keys()):
                if over <= 0:
                    break
                kill_credit[locker] -= 1
                over -= 1
        self.kill_credit = kill_credit
        # agent 日志 [KILL] 名单交叉核验（写入结果供报告）
        self.agent_kill_names = agent_kill_names or []
        self.brk_names = brk_names
        self.oob_names = oob_names
        res = {}
        for n in known_usv:
            if n in brk_names:
                res[n] = "breakthrough"
            elif n in oob_names:
                res[n] = "out_of_bounds"
            elif agent_kill_names and n in agent_kill_names:
                res[n] = "combat_killed"
            elif black_killed == bu:
                res[n] = "combat_killed"   # 全灭：未特别识别者归 combat
            else:
                res[n] = "survived"
        return {
            "enemy_terminal": res,
            "enemy_combat_killed": combat_count,
            "enemy_out_of_bounds": oob_count,
            "enemy_breakthrough_events": brk_count,
            "enemy_survived": survived,
            "enemy_unknown": unknown,
            "enemy_breakthrough_reward": brk_reward,
            "black_killed_reward": black_killed,
            "brk_names": brk_names,
            "oob_names": oob_names,
            "kill_credit": dict(kill_credit),
            "oob_events": [{"unit": n, "unit_type": "USV" if "usv" in n else "UAV",
                            "oob_time": self.enemy[n]["oob_time"],
                            "oob_x": self.enemy[n]["oob_pos"][0] if self.enemy[n]["oob_pos"] else None,
                            "oob_y": self.enemy[n]["oob_pos"][1] if self.enemy[n]["oob_pos"] else None,
                            "terminal": res.get(n, "unknown")}
                           for n in oob_names],
            "enemy_usv_combat_killed": combat_count,
            "enemy_uav_combat_killed": 0,   # 白方无法 combat 击杀敌 UAV（无 plane locker）
        }

    # ── 输出 ──
    def friendly_deaths(self):
        out = []
        for name, f in self.friendly.items():
            out.append({"unit": name, "type": f["type"], "alive": f["alive"],
                        "death_time": f["death_time"], "death_cause": f["death_cause"]})
        return out

    def unit_rows(self):
        rows = []
        for name, f in self.friendly.items():
            rows.append({
                "unit": name, "unit_type": f["type"],
                "explored_area_km2": round(self.explorer.unit_explored_km2(name), 1),
                "first_coverage_area_km2": round(self.explorer.first_coverage_km2(name), 1),
                "damage_hits": self.hit_credit.get(name, 0),
                "kill_credit": self.kill_credit.get(name, 0),
                "targets_damaged": len(self.usv_targets.get(name, set())),
                "alive": f["alive"],
                "death_time": f["death_time"],
                "death_cause": f["death_cause"],
            })
        return rows

    def summary(self):
        deaths = self.friendly_deaths()
        usv_dead = sum(1 for d in deaths if d["type"] == "USV" and not d["alive"])
        uav_dead = sum(1 for d in deaths if d["type"] == "UAV" and not d["alive"])
        total_explored = self.explorer.total_explored_km2()
        return {
            "friendly_usv_dead": usv_dead,
            "friendly_uav_dead": uav_dead,
            "friendly_total_dead": usv_dead + uav_dead,
            "total_explored_area_km2": round(total_explored, 1),
            "exploration_ratio": round(self.explorer.exploration_ratio(self.valid_area_km2), 4),
            "sum_unit_explored_km2": round(sum(self.explorer.unit_explored_km2(u) for u in self.explorer.unit_cells), 1),
            "sum_damage_hits": sum(self.hit_credit.values()),
            "sum_kill_credit": sum(self.kill_credit.values()),
        }
