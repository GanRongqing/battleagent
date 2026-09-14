#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""auto_harness/phase0/code/analyze_corpus.py — corpus analysis (deterministic miner + reports).

Reads AUTO_HARNESS_EPISODES.csv + episode logs, derives features, classifies failure events,
writes analysis CSVs + summary/top-targets/retrospective markdown and prints terminal block.
"""
import csv
import glob
import json
import os
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
P0 = os.path.join(ROOT, "auto_harness", "phase0")
sys.path.insert(0, os.path.join(P0, "code"))
from trace_derive import parse_episode_log      # noqa: E402
from failure_miner import analyze_episode       # noqa: E402
from failure_taxonomy import TAXONOMY           # noqa: E402
CORP = os.path.join(P0, "corpus")
ANAL = os.path.join(P0, "analysis")
os.makedirs(ANAL, exist_ok=True)


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / den
    return (c - h, c + h)


def main():
    epi = os.path.join(CORP, "AUTO_HARNESS_EPISODES.csv")
    rows = list(csv.DictReader(open(epi))) if os.path.exists(epi) else []
    rows = [r for r in rows if r.get("seed", "").isdigit()]
    n = len(rows)
    logs = {os.path.basename(p): p for p in glob.glob(os.path.join(CORP, "logs", "*.log"))}
    feats, analyses = {}, {}
    for r in rows:
        p = logs.get(f"S2_B3_s{int(r['seed'])}.log")
        if not p:
            continue
        f = parse_episode_log(p)
        f["clean_win"]=int(r.get("clean_win",0) or 0); f["breakthrough"]=int(r.get("breakthrough",0) or 0);
        f["outcome"]=r.get("outcome"); f["friendly_usv_loss"]=int(r.get("friendly_usv_loss",0) or 0)
        feats[r["seed"]] = f
        analyses[r["seed"]] = analyze_episode(f)
    clean = sum(1 for r in rows if int(r.get("clean_win", 0) or 0) == 1)
    brk = sum(1 for r in rows if int(r.get("breakthrough", 0) or 0) > 0)
    defe = sum(1 for r in rows if r.get("outcome") == "DEFEAT")
    fails = [r for r in rows if not (int(r.get("clean_win", 0) or 0))]
    lo, hi = wilson(clean, n)
    print(f"corpus episodes={n} clean={clean} ({clean/max(1,n):.3f}) wilsonCI=[{lo:.3f},{hi:.3f}] "
          f"brk={brk} defeats={defe} failures={len(fails)}")
    # failure mode counts
    from collections import Counter
    prim = Counter(a["primary"] for a in analyses.values() if a["primary"])
    print("primary modes:", dict(prim))
    # write derived episodes (merge features)
    cols = list(rows[0].keys()) + ["first_lock", "first_kill", "reacquire_attempts",
                                   "reacquire_success", "first_friendly_death_time",
                                   "lost_track_runs", "capacity_hole_proxy_steps"]
    out_path = os.path.join(ANAL, "AUTO_HARNESS_DERIVED.csv")
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            fts = feats.get(r["seed"], {})
            rr = dict(r)
            for k in ("first_lock", "first_kill", "reacquire_attempts", "reacquire_success",
                      "first_friendly_death_time", "lost_track_runs", "capacity_hole_proxy_steps"):
                rr[k] = fts.get(k)
            w.writerow(rr)
    # success vs failure compare (a few discriminative features)
    comp = {}
    for key in ("first_detection", "lost_track_runs", "capacity_hole_proxy_steps",
                "reacquire_attempts"):
        succ = [float(feats[s][key]) for s in feats if feats[s].get("clean_win",1)==1 and
                feats[s].get(key) is not None]
        fa = [float(feats[s][key]) for s in feats if feats[s].get("clean_win",0)!=1 and
              feats[s].get(key) is not None]
        comp[key] = (statistics.mean(succ) if succ else None,
                     statistics.mean(fa) if fa else None)
    print("succ-vs-fail means:", {k: (round(v[0],1) if v[0] is not None else None,
                                      round(v[1],1) if v[1] is not None else None)
                                   for k, v in comp.items()})
    print("[done analysis on", n, "episodes]")


if __name__ == "__main__":
    sys.exit(main())
