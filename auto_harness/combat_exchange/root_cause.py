#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""root_cause.py — reconstruct kill chain + white death context from agent log + game log.

Produces (under auto_harness/combat_exchange/):
  02_COMBAT_FUNNEL.csv, 03_WHITE_DEATH_CONTEXT.csv, 04_KILL_CHAIN_FAILURES.csv,
  05_ROOT_CAUSE_RANKING.csv, 06_ROOT_CAUSE_REPORT.md

Note: [ASSIGN] is a STEP-LEVEL PROXY, not canonical allocation (frozen W5 has no canonical
allocator instrumentation). It is used here only for offline diagnosis, clearly labeled.
"""
import csv
import glob
import json
import os
import re

ROOT = "/root/autodl-tmp/hsystem"
EVAL = os.path.join(ROOT, "auto_harness", "six_strategy_w5_eval")
OUT = os.path.join(ROOT, "auto_harness", "combat_exchange")
GAME_DIR = os.path.join(ROOT, "hsystem", "pomdp_api", "api_logs", "games")

NAME = {
    1: "横向编队-中央汇聚箭头突防", 2: "菱形编队-接近后扇形展开突防",
    3: "菱形编队-两翼包抄中央突进", 4: "菱形编队-南北两翼镜像夹击",
    5: "菱形编队-中央汇聚箭头突防", 6: "菱形编队-MUSV外侧绕行SUSV中央收缩",
}

def load_episodes():
    rows = list(csv.DictReader(open(os.path.join(EVAL, "SIX_STRATEGY_W5_EPISODES.csv"))))
    return rows

def parse_agent_log(path):
    """Return timeline of events with sim-time."""
    text = open(path, encoding="utf-8", errors="replace").read()
    t = 0.0
    detects, assigns, kills, releases = [], [], [], []
    for line in text.splitlines():
        m = re.search(r"\[t=([0-9,]+)s\]", line)
        if m:
            t = float(m.group(1).replace(",", ""))
        for mm in re.finditer(r"\[DETECT\]\s+(\S+)", line):
            detects.append((t, mm.group(1)))
        for mm in re.finditer(r"\[ASSIGN\]\s+(\S+)->(\S+)", line):
            assigns.append((t, mm.group(1), mm.group(2)))
        for mm in re.finditer(r"\[RELEASE\]\s+(\S+)->(\S+)", line):
            releases.append((t, mm.group(1), mm.group(2)))
        for mm in re.finditer(r"\[KILL\]\s+(\S+)", line):
            kills.append((t, mm.group(1)))
    return {"detects": detects, "assigns": assigns, "kills": kills, "releases": releases}

def parse_game_log(path):
    """Return per-step white USV states + enemy contacts, and white death times."""
    d = json.load(open(path, encoding="utf-8"))
    steps = d.get("steps", [])
    # white usv lifecycle
    alive_at = {}   # usv -> last time seen alive
    dead_at = {}    # usv -> first time seen dead
    usv_states_by_time = []
    enemy_by_time = []
    for s in steps:
        st = s.get("sim_time", 0.0)
        usvs = s.get("usv_states", [])
        enemies = s.get("active_enemies", []) + s.get("passive_enemies", [])
        usv_states_by_time.append((st, usvs))
        enemy_by_time.append((st, enemies))
        for u in usvs:
            nm = u.get("name")
            if u.get("is_alive"):
                alive_at[nm] = st
            else:
                if nm not in dead_at:
                    dead_at[nm] = st
    return {"usv_states_by_time": usv_states_by_time, "enemy_by_time": enemy_by_time,
            "dead_at": dead_at, "alive_at": alive_at, "steps": steps,
            "result": d.get("result"), "result_reason": d.get("result_reason")}

def nearest_friendly(usv, usvs, exclude=None):
    best = None
    for u in usvs:
        if not u.get("is_alive"):
            continue
        if exclude and u.get("name") == exclude:
            continue
        p = u.get("position")
        if p:
            d = ((p[0] - usv[0])**2 + (p[1] - usv[1])**2) ** 0.5
            if best is None or d < best:
                best = d
    return best

def main():
    episodes = load_episodes()
    funnel_rows = []
    death_rows = []
    fail_counts = {f"KC-F{i}": 0 for i in range(1, 11)}
    fail_by_strategy = {}

    for ep in episodes:
        sid = int(ep["strategy_id"]); seed = ep["seed"]
        gl_name = ep.get("game_log", "")
        gl_path = os.path.join(GAME_DIR, gl_name) if gl_name else None
        if not gl_path or not os.path.exists(gl_path):
            continue
        alog = parse_agent_log(os.path.join(EVAL, "runs", f"strategy_{sid}", f"seed_{seed}.log"))
        glog = parse_game_log(gl_path)

        detected = {}
        for t, nm in alog["detects"]:
            detected.setdefault(nm, t)
        killed = {}
        for t, nm in alog["kills"]:
            killed.setdefault(nm, t)
        # assigned targets + who
        assigned = {}   # target -> set of white usv
        first_assign = {}
        for t, w, tgt in alog["assigns"]:
            assigned.setdefault(tgt, set()).add(w)
            first_assign.setdefault(tgt, t)
        # attackers count (max distinct white assigned to a target)
        attacker_counts = {tgt: len(ws) for tgt, ws in assigned.items()}

        # funnel per target
        for tgt, dt in detected.items():
            is_killed = tgt in killed
            was_assigned = tgt in assigned
            kt = killed.get(tgt, "")
            at = first_assign.get(tgt, "")
            n_attackers = attacker_counts.get(tgt, 0)
            # attackers that died before kill
            attackers_died = 0
            for w in assigned.get(tgt, set()):
                if w in glog["dead_at"]:
                    wd = glog["dead_at"][w]
                    if not is_killed or (wd <= kt):
                        attackers_died += 1
            outcome = "KILLED" if is_killed else "NOT_KILLED"
            funnel_rows.append({
                "strategy": sid, "seed": seed, "target_id": tgt,
                "detected": round(dt, 1), "allocated": "PROXY" if was_assigned else "NO",
                "first_assign_time": round(at, 1) if at else "",
                "number_of_attackers": n_attackers,
                "first_lock_time": "NOT_MEASURED", "lock_duration": "NOT_MEASURED",
                "first_hit_time": "NOT_MEASURED", "kill_time": round(kt, 1) if kt else "",
                "target_outcome": outcome,
            })
            # classify non-killed targets
            if not is_killed:
                if not was_assigned:
                    f = "KC-F1"
                elif tgt not in killed and any(w in glog["dead_at"] for w in assigned.get(tgt, set())):
                    f = "KC-F5"
                else:
                    f = "KC-F9"
                fail_counts[f] += 1
                fail_by_strategy.setdefault(f, set()).add(sid)

        # white death context
        for w, dtime in glog["dead_at"].items():
            # find state near death (last alive state)
            usv_last = None
            for st, usvs in glog["usv_states_by_time"]:
                for u in usvs:
                    if u.get("name") == w and u.get("is_alive"):
                        usv_last = (st, u)
            if not usv_last:
                continue
            st, u = usv_last
            pos = u.get("position")
            is_locking = u.get("is_locking")
            locked_attacker = u.get("locked_attacker") or []
            # nearby friendlies
            friends = 0; nearest = None
            for st2, usvs in glog["usv_states_by_time"]:
                if st2 == st:
                    for u2 in usvs:
                        if u2.get("name") == w or not u2.get("is_alive"):
                            continue
                        p2 = u2.get("position")
                        if p2 and pos:
                            d = ((p2[0]-pos[0])**2 + (p2[1]-pos[1])**2)**0.5
                            if d < 50000:
                                friends += 1
                            if nearest is None or d < nearest:
                                nearest = d
            death_rows.append({
                "strategy": sid, "seed": seed, "white_usv": w, "death_time": round(dtime, 1),
                "had_valid_lock": is_locking,
                "enemies_locking_this_usv": len(locked_attacker),
                "nearby_friendly_usv_50km": friends,
                "distance_nearest_support": round(nearest, 1) if nearest is not None else "",
                "position": [round(x, 1) for x in pos] if pos else "",
            })

    # write funnel
    with open(os.path.join(OUT, "02_COMBAT_FUNNEL.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(funnel_rows[0].keys()) if funnel_rows else ["x"])
        w.writeheader()
        for r in funnel_rows:
            w.writerow(r)
    # write death context
    with open(os.path.join(OUT, "03_WHITE_DEATH_CONTEXT.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(death_rows[0].keys()) if death_rows else ["x"])
        w.writeheader()
        for r in death_rows:
            w.writerow(r)
    # failures
    with open(os.path.join(OUT, "04_KILL_CHAIN_FAILURES.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["failure_class", "count", "coverage_pct", "num_strategies"])
        tot = sum(fail_counts.values()) or 1
        for k in sorted(fail_counts):
            w.writerow([k, fail_counts[k], round(fail_counts[k]/tot*100, 1),
                        len(fail_by_strategy.get(k, set()))])
    # ranking
    with open(os.path.join(OUT, "05_ROOT_CAUSE_RANKING.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["rank", "failure_class", "count", "coverage_pct", "num_strategies"])
        ranked = sorted(fail_counts.items(), key=lambda kv: -kv[1])
        for i, (k, c) in enumerate(ranked, 1):
            w.writerow([i, k, c, round(c/tot*100, 1), len(fail_by_strategy.get(k, set()))])

    print("=== KILL CHAIN FAILURES ===")
    for k, c in sorted(fail_counts.items(), key=lambda kv: -kv[1]):
        print(f"{k}: {c} ({round(c/tot*100,1)}%) strategies={len(fail_by_strategy.get(k,set()))}")
    print("total non-killed detected targets:", tot)
    # death context summary
    isolated = sum(1 for r in death_rows if r["nearby_friendly_usv_50km"] < 2)
    print(f"\n=== WHITE DEATHS ===")
    print(f"total deaths: {len(death_rows)}, isolated (<2 friendly in 50km): {isolated}")
    no_lock = sum(1 for r in death_rows if not r["had_valid_lock"])
    print(f"died without valid lock: {no_lock}")

if __name__ == "__main__":
    main()
