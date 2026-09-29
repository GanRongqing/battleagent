#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""run_c4_eval.py — Stage B driver: run ACE vs C4 on S1/S6 x fresh seeds (paired).

Calls run_combat.py per (policy, strategy, seed) with a hard wall-clock timeout, captures the
per-episode JSON summary + the raw agent log, and writes 01_EPISODE_RESULTS.csv.

Usage: python run_c4_eval.py [--timeout 1800] [--seeds 20001,20002,20003,20004]
                             [--strategies 1,6] [--policies expand,reach]
"""
import argparse
import csv
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = "/root/miniconda3/envs/hsystem_env/bin/python"
BASE = os.path.join(ROOT, "auto_harness", "combat_exchange", "c4_reachability_weighted_commitment")
RAW = os.path.join(BASE, "fresh_eval", "raw")
SEEDFILE = "/tmp/opencode/seed_w0.txt"
STRAT_NAME = {1: "S1", 6: "S6"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--seeds", default="20001,20002,20003,20004")
    ap.add_argument("--strategies", default="1,6")
    ap.add_argument("--policies", default="expand,reach")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    seeds = [int(s) for s in args.seeds.split(",")]
    strats = [int(s) for s in args.strategies.split(",")]
    pols = args.policies.split(",")
    os.makedirs(RAW, exist_ok=True)
    rows = []
    for pol in pols:
        for s in strats:
            for seed in seeds:
                tag = f"{pol}_{STRAT_NAME[s]}"
                logdir = os.path.join(RAW, tag)
                os.makedirs(logdir, exist_ok=True)
                cmd = [PY, os.path.join(ROOT, "run_combat.py"), "--agent", pol,
                       "--strategy", str(s), "--seed", str(seed), "--port", str(args.port),
                       "--seed-file", SEEDFILE, "--tag", tag, "--logdir", logdir]
                t0 = time.time()
                try:
                    out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                                         timeout=args.timeout)
                    line = [l for l in out.stdout.strip().splitlines() if l.startswith("{")]
                    rec = json.loads(line[-1]) if line else {}
                    timed_out = False
                except subprocess.TimeoutExpired:
                    rec = {}
                    timed_out = True
                wall = round(time.time() - t0, 1)
                # terminal / cutoff from the agent log
                logf = os.path.join(logdir, f"s{s}_{tag}_seed{seed}.log")
                text = open(logf, encoding="utf-8", errors="replace").read() if os.path.exists(logf) else ""
                valid = ("[META]" in text)
                last_t = ""
                for l in text.splitlines()[::-1]:
                    if l.startswith("[t="):
                        last_t = l.split("]", 1)[0].replace("[t=", "")
                        break
                row = {"policy": pol, "strategy": STRAT_NAME[s], "seed": seed,
                       "black_kills": rec.get("black_kills"), "white_usv_losses": rec.get("white_usv_losses"),
                       "CER": rec.get("CER"), "exchange_result": rec.get("exchange_result"),
                       "wall_s": wall, "timed_out": timed_out, "valid": valid, "last_sim_t": last_t,
                       "logfile": logf}
                rows.append(row)
                print(json.dumps(row, ensure_ascii=False), flush=True)
                with open(os.path.join(BASE, "fresh_eval", "01_EPISODE_RESULTS.csv"), "w",
                          newline="", encoding="utf-8") as f:
                    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                    w.writeheader(); w.writerows(rows)
    print("DONE", len(rows), "episodes")


if __name__ == "__main__":
    main()
