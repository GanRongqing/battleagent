#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""coevolution_final/overlay_confirm.py — W6_OVERLAY variant DEV confirm.

W6_OVERLAY = predictive_intercept + uav_track_maintenance + adaptive_screen +
breakthrough_horizon (NO pursuit_cost, NO handoff) => w6_allocation passes the frozen
base allocator through unchanged. Tests whether the disruptive allocation layer (both
collapse and preserve variants showed seed-dependent 5-USV collapses on B3) was the
cause, and whether the overlay-only adaptation is robustly clean.

N=1 per DEV seed (deterministic). Seeds: B0 2001, B3 2001/2002/2003 (+ B3 holdout
s4004 spot check is NOT used to keep holdout clean).
"""
import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from w6_dev_runner import run_one  # noqa: E402

OUT = os.path.dirname(os.path.abspath(__file__))
COLS = ["opponent_profile", "seed", "white_version", "result", "clean_win",
        "enemy_kills", "friendly_usv_dead", "breakthrough", "resolution_time",
        "screen_assignments", "unique_screen_reconfigurations",
        "track_maintenance_assignments", "unsafe_close_entries",
        "min_target_distance_during_pursuit"]
PLAN = [("B0_RANDOM", 2001, "W6_OVERLAY"), ("B3_ADAPTIVE", 2001, "W6_OVERLAY"),
        ("B3_ADAPTIVE", 2002, "W6_OVERLAY"), ("B3_ADAPTIVE", 2003, "W6_OVERLAY")]


def read_json(p):
    try:
        return json.load(open(p))
    except Exception:
        return {}


def main():
    path = os.path.join(OUT, "overlay_confirm.csv")
    done = set()
    if os.path.exists(path):
        done = {(r["opponent_profile"], int(r["seed"])) for r in csv.DictReader(open(path))}
    for profile, seed, ver in PLAN:
        if (profile, seed) in done:
            continue
        print(f"[OVERLAY] S1 {profile} s{seed} {ver} ...", flush=True)
        row = run_one("S1", profile, seed, ver)
        d = read_json("/tmp/opencode/w6_metrics.json")
        row["screen_assignments"] = d.get("screen_assignments", 0)
        row["unique_screen_reconfigurations"] = d.get("unique_screen_reconfigurations", 0)
        row["track_maintenance_assignments"] = d.get("track_maintenance_assignments", 0)
        row["unsafe_close_entries"] = d.get("unsafe_close_entries", 0)
        row["min_target_distance_during_pursuit"] = d.get("min_target_distance_during_pursuit", 0)
        new = not os.path.exists(path)
        with open(path, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=COLS)
            if new:
                w.writeheader()
            w.writerow({k: row.get(k) for k in COLS})
        print(f"   -> {row['result']} clean={row['clean_win']} "
              f"usv_dead={row['friendly_usv_dead']} brk={row['breakthrough']}", flush=True)
    print("[done]")


if __name__ == "__main__":
    sys.exit(main())
