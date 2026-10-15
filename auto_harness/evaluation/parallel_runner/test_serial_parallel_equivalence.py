#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_serial_parallel_equivalence.py — serial vs parallel must be bit-identical per episode.

Runs a configurable workload with --workers 1 and --workers N (N>=2, so multiple episodes are active
at once) and compares, for each (Strategy,Policy,Seed): the game-log trajectory hash, the outcome
(kills/losses), terminal result, and the actual engine seed.

Usage: python test_serial_parallel_equivalence.py [--strategies W2-1,W2-4] [--seeds 43001] [--parallel 2]
"""
import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import parallel_runner as pr  # noqa: E402


def traj_hash(game_log):
    d = json.load(open(game_log, encoding="utf-8"))
    items = [[u.get("name"), u.get("is_alive"), round((u.get("position") or [0, 0])[0], 3),
              round((u.get("position") or [0, 0])[1], 3), u.get("is_locked"), u.get("is_locking")]
             for s in d["steps"] for u in s.get("usv_states", [])]
    return hashlib.sha256(json.dumps(items).encode()).hexdigest()[:16], d["total_steps"], d["result"]


def collect(results_dir):
    out = {}
    for f in os.listdir(results_dir):
        if not f.endswith(".json"):
            continue
        d = json.load(open(os.path.join(results_dir, f), encoding="utf-8"))
        r = d.get("Result", {})
        key = (d["Strategy"], d["Policy"], d["Seed"])
        base = os.path.join(pr.OUTROOT, d.get("run_game_dir", ""))
        # game log path is stored per worker; find via basename in results (worker-relative). We store
        # only basename; locate newest matching under all parallel run dirs.
        out[key] = r
    return out


def run_mode(args, workers, run_id):
    ns = argparse.Namespace(**vars(args))
    ns.workers = workers; ns.run_id = run_id; ns.resume = False; ns.dry_run = False
    ns.benchmark = False; ns.epoch = "EQ"; ns.max_attempts = 1
    pr.run(ns)


def find_game_log(basename):
    if not basename:
        return None
    base = "/tmp/opencode/parallel_runs"
    hit = None
    for root, _d, files in os.walk(base):
        if basename in files:
            hit = os.path.join(root, basename)
    return hit


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategies", default="W2-1,W2-4")
    ap.add_argument("--seeds", default="43001")
    ap.add_argument("--policies", default="ACE")
    ap.add_argument("--parallel", type=int, default=2)
    a = ap.parse_args()
    run_mode(a, 1, "eq_serial")
    run_mode(a, a.parallel, "eq_parallel")
    ser = collect("/tmp/opencode/parallel_runs/eq_serial/results")
    par = collect("/tmp/opencode/parallel_runs/eq_parallel/results")
    keys = sorted(set(ser) | set(par))
    ok = True
    for k in keys:
        s, p = ser.get(k), par.get(k)
        if not s or not p:
            print("MISSING", k); ok = False; continue
        hs = traj_hash(find_game_log(s.get("Game_Log"))) if s.get("Valid") else None
        hp = traj_hash(find_game_log(p.get("Game_Log"))) if p.get("Valid") else None
        same = (s.get("Black_Killed"), s.get("White_USV_Lost"), s.get("Terminal_Result"), s.get("Actual_Engine_Seed"), hs) == \
               (p.get("Black_Killed"), p.get("White_USV_Lost"), p.get("Terminal_Result"), p.get("Actual_Engine_Seed"), hp)
        print(f"{k} serial={hs} parallel={hp} identical={same}")
        ok = ok and same
    print("test_serial_parallel_equivalence:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
