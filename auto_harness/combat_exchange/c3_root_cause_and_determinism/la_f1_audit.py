#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""la_f1_audit.py — decompose LA-F1 (assigned but never reached lock range) into subcauses.

0 new episodes: reuses W5 baseline agent logs + reliable baseline game logs (11001/11002).
For every (USV,target) assignment that never yields a lock command, reconstruct the approach timeline
(distance, visibility, USV course) and classify a single primary subcause. Also builds the
successful-lock control group for feature comparison.
"""
import csv
import json
import math
import os
import re
from collections import defaultdict

ROOT = "/root/autodl-tmp/hsystem"
EVAL = os.path.join(ROOT, "auto_harness", "six_strategy_w5_eval")
GAME = os.path.join(ROOT, "hsystem", "pomdp_api", "api_logs", "games")
OUT = os.path.join(ROOT, "auto_harness", "combat_exchange", "c3_root_cause_and_determinism", "la_f1_audit")
LOCK_RANGE = 40000.0
W300, W600 = 300.0, 600.0


def build(ep):
    sid = int(ep["strategy_id"]); seed = ep["seed"]; gl = ep.get("game_log", "")
    gp = os.path.join(GAME, gl)
    if not os.path.exists(gp):
        return None
    alog = open(os.path.join(EVAL, "runs", f"strategy_{sid}", f"seed_{seed}.log"),
                encoding="utf-8", errors="replace").read()
    assigns = []
    t = 0.0
    for line in alog.splitlines():
        m = re.search(r"\[t=([0-9,]+)s\]", line)
        if m:
            t = float(m.group(1).replace(",", ""))
        for mm in re.finditer(r"\[ASSIGN\]\s+(white_usv\d+)->([^(\s]+)", line):
            assigns.append((t, mm.group(1), mm.group(2)))
    d = json.load(open(gp))
    locks = set()
    usv = defaultdict(dict); enemy = defaultdict(dict); dead = {}
    steps = []
    for s in d["steps"]:
        st = s["sim_time"]; steps.append(st)
        for u in s.get("usv_states", []):
            if u.get("is_alive"):
                usv[u["name"]][st] = (u.get("position"), u.get("course"))
            elif u["name"] not in dead:
                dead[u["name"]] = st
        for e in s.get("active_enemies", []):
            enemy[e["name"]][st] = e.get("position")
        for a in s.get("actions", []):
            lm = re.search(r"(white_usv\d+) 锁定 (usv\d+)", a.get("动作", ""))
            if lm:
                locks.add((lm.group(1), lm.group(2)))
    return dict(sid=sid, seed=seed, assigns=assigns, locks=locks, usv=usv, enemy=enemy, dead=dead, steps=sorted(steps))


def metrics(ep, t0, w, tg):
    steps = [st for st in ep["steps"] if st >= t0]
    if not steps:
        return None
    vis = 0; tot = 0; ds = []; courses = []
    for st in steps:
        up = ep["usv"][w].get(st)
        epos = ep["enemy"][tg].get(st)
        if up is None:
            continue
        tot += 1
        courses.append(up[1])
        if epos:
            vis += 1
            ds.append((st, math.hypot(up[0][0] - epos[0], up[0][1] - epos[1])))
    if not ds:
        return dict(visible_frac=0.0, min_d=None, close300=None, close600=None,
                    pos_frac=0.0, osc=0.0, died=ep["dead"].get(w))
    dmin = min(x[1] for x in ds)
    def prog(window):
        base = ds[0][0]
        seg = [x for x in ds if x[0] <= base + window]
        if len(seg) < 2:
            return None
        return seg[0][1] - seg[-1][1]  # positive = closed
    pos_frac = sum(1 for i in range(1, len(ds)) if ds[i][1] < ds[i - 1][1]) / max(1, len(ds) - 1)
    # course oscillation: mean abs step-to-step course change (wrapped)
    ch = 0.0; n = 0
    for i in range(1, len(courses)):
        if courses[i - 1] is None or courses[i] is None:
            continue
        dv = abs((courses[i] - courses[i - 1] + 180) % 360 - 180)
        ch += dv; n += 1
    osc = ch / n if n else 0.0
    return dict(visible_frac=vis / max(1, tot), min_d=dmin, close300=prog(W300), close600=prog(W600),
                pos_frac=pos_frac, osc=osc, died=ep["dead"].get(w))


def classify(m, t0):
    if m is None:
        return "LA1-I_OTHER"
    if m["died"] is not None and m["min_d"] is not None and m["min_d"] >= LOCK_RANGE:
        return "LA1-E_WHITE_DIED_BEFORE_CLOSURE"
    if m["visible_frac"] < 0.5:
        return "LA1-A_TRACK_LOST_DURING_APPROACH"
    c = m["close600"] if m["close600"] is not None else m["close300"]
    if c is not None and c <= 0:
        return "LA1-C_NO_CLOSING_PROGRESS"
    if m["osc"] > 30.0:
        return "LA1-D_GEOMETRY_OSCILLATION"
    if m["min_d"] is not None and m["min_d"] < LOCK_RANGE * 1.15:
        return "LA1-F_LEGAL_LOCK_MISSED"
    return "LA1-I_OTHER"


def main():
    rows = list(csv.DictReader(open(os.path.join(EVAL, "SIX_STRATEGY_W5_EPISODES.csv"))))
    timelines = []; subcauses = defaultdict(int); by_strat = defaultdict(lambda: defaultdict(int))
    success = []; failure = []
    for ep in rows:
        E = build(ep)
        if not E:
            continue
        for t0, w, tg in E["assigns"]:
            m = metrics(E, t0, w, tg)
            if m is None:
                continue
            locked = (w, tg) in E["locks"]
            rec = dict(strategy=E["sid"], seed=E["seed"], usv=w, target=tg, t=t0, locked=locked, **m)
            timelines.append(rec)
            if locked:
                success.append(m)
            else:
                cls = classify(m, t0)
                subcauses[cls] += 1; by_strat[E["sid"]][cls] += 1
                failure.append((cls, m))
    # write
    with open(os.path.join(OUT, "01_ASSIGNMENT_TIMELINES.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(timelines[0].keys())); w.writeheader()
        for r in timelines: w.writerow(r)
    nl = sum(subcauses.values()) or 1
    with open(os.path.join(OUT, "03_LA_F1_SUBCAUSES.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["subcause", "count", "share", "strategies"])
        for k in sorted(subcauses, key=lambda x: -subcauses[x]):
            strat = [s for s in by_strat if by_strat[s].get(k)]
            w.writerow([k, subcauses[k], round(subcauses[k] / nl, 3), len(strat)])
    def mean(x, key):
        vals = [r[key] for r in x if r.get(key) is not None]
        return sum(vals) / len(vals) if vals else 0.0
    with open(os.path.join(OUT, "02_SUCCESS_VS_FAILURE.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["group", "visible_frac", "mean_osc", "mean_close600", "mean_pos_frac"])
        w.writerow(["success", round(mean(success, "visible_frac"), 3), round(mean(success, "osc"), 1),
                    round(mean(success, "close600"), 1), round(mean(success, "pos_frac"), 3)])
        fm = [m for _, m in failure]
        w.writerow(["LA-F1_failure", round(mean(fm, "visible_frac"), 3), round(mean(fm, "osc"), 1),
                    round(mean(fm, "close600"), 1), round(mean(fm, "pos_frac"), 3)])
    print(f"assignments total={len(timelines)} locked={len(success)} nolock={len(failure)}")
    print("=== LA-F1 subcauses ===")
    for k in sorted(subcauses, key=lambda x: -subcauses[x]):
        strat = [s for s in by_strat if by_strat[s].get(k)]
        print(f"  {k}: {subcauses[k]} ({subcauses[k]/nl*100:.1f}%) strategies={len(strat)}")
    print("=== success vs failure means ===")
    for label, grp in [("success", success), ("failure", [m for _, m in failure])]:
        print(f"  {label}: visible={mean(grp,'visible_frac'):.2f} osc={mean(grp,'osc'):.1f} "
              f"close600={mean(grp,'close600'):.0f} pos_frac={mean(grp,'pos_frac'):.2f}")


if __name__ == "__main__":
    main()
