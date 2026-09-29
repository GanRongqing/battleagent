#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""audit_retreats.py — reconstruct C1 retreat-eligible events from game logs and classify.

Approximation of C1's trigger: exposed (is_locked or locked_attacker) AND no enemy within
LOCK_RANGE (40km) AND nearest friendly > 50km. Then classify the enemy's motion toward the
USV as CLOSING (attacking) vs PASSING (transiting), using the enemy velocity vector.

Outputs C1_RETREAT_EVENT_AUDIT.csv with per-strategy counts.
"""
import json
import math
import os
import csv

ROOT = "/root/autodl-tmp/hsystem"
GAME_DIR = os.path.join(ROOT, "hsystem", "pomdp_api", "api_logs", "games")
OUT = os.path.join(ROOT, "auto_harness", "combat_exchange")

# C1 seed11001 game logs (matched by script_name + sim_duration)
MAP = {
    1: "game_5_20260926_225015.json",   # 横向编队-中央汇聚箭头突防
    2: "game_3_20260926_220925.json",   # 菱形编队-接近后扇形展开突防
    3: "game_6_20260926_230518.json",   # 菱形编队-两翼包抄中央突进
    4: "game_7_20260926_232304.json",   # 菱形编队-南北两翼镜像夹击
    5: "game_4_20260926_222548.json",   # 菱形编队-中央汇聚箭头突防
    6: "game_8_20260926_233811.json",   # 菱形编队-MUSV外侧绕行SUSV中央收缩
}
LOCK_RANGE = 40_000.0
SUPPORT_RANGE = 50_000.0


def main():
    rows = []
    totals = {"TRUE_SURVIVAL_RETREAT": 0, "PASSING_TARGET_FALSE_RETREAT": 0,
              "KILL_OPPORTUNITY_ABORTED": 0, "UNCLEAR": 0}
    per_strategy = {}
    for sid in range(1, 7):
        p = os.path.join(GAME_DIR, MAP[sid])
        d = json.load(open(p, encoding="utf-8"))
        steps = d.get("steps", [])
        cnt = {"TRUE_SURVIVAL_RETREAT": 0, "PASSING_TARGET_FALSE_RETREAT": 0,
               "KILL_OPPORTUNITY_ABORTED": 0, "UNCLEAR": 0}
        # track consecutive enemy positions for sustained-closing check
        enemy_hist = {}  # name -> list of (sim_time, x, y)
        for s in steps:
            st = s.get("sim_time", 0.0)
            usvs = {u["name"]: u for u in s.get("usv_states", []) if u.get("is_alive")}
            enemies = {e["name"]: e for e in s.get("active_enemies", [])}
            for e in s.get("active_enemies", []):
                hist = enemy_hist.setdefault(e["name"], [])
                pos = e.get("position")
                if pos:
                    hist.append((st, pos[0], pos[1]))
            for nm, u in usvs.items():
                exposed = bool(u.get("is_locked") or u.get("locked_attacker"))
                if not exposed:
                    continue
                pos = u.get("position")
                if not pos:
                    continue
                ux, uy = pos[0], pos[1]
                # kill opportunity: any enemy within LOCK_RANGE
                kill_opp = any(
                    e.get("position") and
                    math.hypot(e["position"][0]-ux, e["position"][1]-uy) < LOCK_RANGE
                    for e in s.get("active_enemies", [])
                )
                # support: nearest friendly
                nearest = None
                for nm2, u2 in usvs.items():
                    if nm2 == nm or not u2.get("position"):
                        continue
                    dd = math.hypot(u2["position"][0]-ux, u2["position"][1]-uy)
                    nearest = dd if nearest is None else min(nearest, dd)
                if kill_opp:
                    # C1 would NOT retreat here (kill opportunity). Not counted.
                    continue
                if nearest is not None and nearest < SUPPORT_RANGE:
                    continue  # support nearby -> no retreat

                # retreat-eligible. classify enemy motion (closing vs passing)
                attackers = u.get("locked_attacker") or []
                closing = False
                any_vel = False
                for aname in attackers:
                    e = enemies.get(aname)
                    if e and e.get("position") and e.get("velocity"):
                        ex, ey = e["position"][0], e["position"][1]
                        vx, vy = e["velocity"][0], e["velocity"][1]
                        # closing = enemy velocity has positive projection toward usv
                        rx, ry = ux - ex, uy - ey
                        rn = math.hypot(rx, ry) or 1.0
                        proj = (vx*rx + vy*ry) / rn
                        any_vel = True
                        if proj > 0.5:  # clearly moving toward usv
                            closing = True
                # also check via consecutive position if no velocity
                if not any_vel and attackers:
                    for aname in attackers:
                        hist = enemy_hist.get(aname, [])
                        if len(hist) >= 2:
                            (t0, x0, y0), (t1, x1, y1) = hist[-2], hist[-1]
                            d0 = math.hypot(x0-ux, y0-uy)
                            d1 = math.hypot(x1-ux, y1-uy)
                            if d1 < d0 - 50:  # closing
                                closing = True

                if closing:
                    label = "TRUE_SURVIVAL_RETREAT"
                else:
                    label = "PASSING_TARGET_FALSE_RETREAT"
                cnt[label] += 1
        per_strategy[sid] = cnt
        for k in cnt:
            totals[k] += cnt[k]

    with open(os.path.join(OUT, "C1_RETREAT_EVENT_AUDIT.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["strategy", "TRUE_SURVIVAL_RETREAT", "PASSING_TARGET_FALSE_RETREAT",
                    "KILL_OPPORTUNITY_ABORTED", "UNCLEAR", "false_pct"])
        for sid in range(1, 7):
            c = per_strategy[sid]
            total = c["TRUE_SURVIVAL_RETREAT"] + c["PASSING_TARGET_FALSE_RETREAT"] or 1
            w.writerow([sid, c["TRUE_SURVIVAL_RETREAT"], c["PASSING_TARGET_FALSE_RETREAT"],
                        c["KILL_OPPORTUNITY_ABORTED"], c["UNCLEAR"],
                        round(c["PASSING_TARGET_FALSE_RETREAT"]/total*100, 1)])

    print("=== C1 RETREAT EVENT AUDIT (seed11001, reconstructed) ===")
    for sid in range(1, 7):
        c = per_strategy[sid]
        t = c["TRUE_SURVIVAL_RETREAT"] + c["PASSING_TARGET_FALSE_RETREAT"] or 1
        print(f"S{sid}: true={c['TRUE_SURVIVAL_RETREAT']} false={c['PASSING_TARGET_FALSE_RETREAT']} "
              f"false%={c['PASSING_TARGET_FALSE_RETREAT']/t*100:.0f}%")
    tot = totals["TRUE_SURVIVAL_RETREAT"] + totals["PASSING_TARGET_FALSE_RETREAT"] or 1
    print(f"TOTAL: true={totals['TRUE_SURVIVAL_RETREAT']} false={totals['PASSING_TARGET_FALSE_RETREAT']} "
          f"false%={totals['PASSING_TARGET_FALSE_RETREAT']/tot*100:.0f}%")


if __name__ == "__main__":
    main()
