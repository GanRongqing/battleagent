#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""coevolution_final/dev21_confirm.py — W6-dev2.1 (Fix E screen demand + Fix F screen
deployment) targeted DEV confirmation on the exact seeds that regressed in dev2.

Seeds (DEV seeds 2001-2003, W6 only; N=1 deterministic):
  B3 s2001  (dev2 Defeat -> must flip clean or materially improve)
  B3 s2002  (dev2 Defeat -> must flip clean or materially improve)
  B0 s2001  (dev2 catastrophic 5-dead+breakthrough -> must improve)
  B3 s2003  (dev2 clean  -> must NOT regress)
  B0 s2002  (dev2 clean  -> must NOT regress)

Also runs the paired W5 on the same seeds for direct reference where useful.
"""
import csv
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from w6_dev_runner import run_one  # noqa: E402

OUT = os.path.dirname(os.path.abspath(__file__))

MECH = ["prediction_count", "intercept_count", "handoff_count", "handoff_evaluations",
        "successful_handoff_count", "track_maintenance_assignments", "screen_assignments",
        "screen_evaluations", "unique_screen_reconfigurations",
        "unique_intercept_plan_changes", "unique_high_risk_transitions",
        "critical_risk_entries", "breakthrough_risk_alerts", "late_intercept_events",
        "unsafe_close_entries", "reposition_outward_count",
        "min_target_distance_during_pursuit"]
COLS = ["opponent_profile", "seed", "white_version", "result", "clean_win",
        "enemy_kills", "friendly_usv_dead", "breakthrough", "explored_area_km2",
        "resolution_time"] + MECH
PLAN = [("B0_RANDOM", 2002, "W6"), ("B0_RANDOM", 2001, "W6"),
        ("B3_ADAPTIVE", 2003, "W6"), ("B3_ADAPTIVE", 2001, "W6"),
        ("B3_ADAPTIVE", 2002, "W6")]


def read_json(p):
    try:
        return json.load(open(p))
    except Exception:
        return {}


def main():
    path = os.path.join(OUT, "dev21_confirm.csv")
    done = set()
    if os.path.exists(path):
        done = {(r["opponent_profile"], int(r["seed"]), r["white_version"])
                for r in csv.DictReader(open(path))}
    for profile, seed, ver in PLAN:
        if (profile, seed, ver) in done:
            continue
        print(f"[DEV2.1] S1 {profile} s{seed} {ver} ...", flush=True)
        row = run_one("S1", profile, seed, ver)   # returns dict incl. new mech cols
        d = read_json("/tmp/opencode/w6_metrics.json")
        if os.path.exists("/tmp/opencode/w6_metrics.json"):
            try:
                os.makedirs(os.path.join(OUT, "w6_dumps"), exist_ok=True)
                import shutil
                shutil.copy("/tmp/opencode/w6_metrics.json",
                            os.path.join(OUT, "w6_dumps",
                                         f"dev21_{profile.replace('_', '')}_s{seed}.json"))
            except Exception:
                pass
        for c in MECH:
            row[c] = d.get(c, 0)
        new = not os.path.exists(path)
        with open(path, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=COLS)
            if new:
                w.writeheader()
            w.writerow({k: row.get(k) for k in COLS})
        print(f"   -> {row['result']} clean={row['clean_win']} "
              f"usv_dead={row['friendly_usv_dead']} brk={row['breakthrough']} "
              f"screen={d.get('screen_assignments')} late={d.get('late_intercept_events')}",
              flush=True)
    print("[done]")


if __name__ == "__main__":
    sys.exit(main())
