#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""w7_performance_push/dev_runner.py — run a White harness candidate vs W5 on S2 x B3 x seeds.
Agent entry: full path to a .py whose __main__ runs the harness (v5 or recon-a entry).
"""
import csv
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.dirname(os.path.abspath(__file__))
PY = "/root/miniconda3/envs/hsystem_env/bin/python"
CFG = "/tmp/opencode/rw_cfg.txt"
API = "http://127.0.0.1:8000"
COLS = ["candidate", "seed", "result", "clean_win", "enemy_kills", "friendly_usv_dead",
        "breakthrough", "explored_area_km2", "resolution_time", "wall_s"]


def http_get(path):
    import urllib.request
    try:
        with urllib.request.urlopen(API + path, timeout=6) as r:
            return r.status
    except Exception:
        return None


def parse_meta(text):
    def g(k, d=None):
        m = re.search(rf"\[META\].*?\b{k}=(\S+)", text)
        v = m.group(1) if m else d
        return d if v in (None, "None", "") else v
    return {"result": g("result", "?"), "vt": float(g("victory_time", 0.0)),
            "dead": float(g("friendly_usv_losses", 0.0)),
            "kills": float(g("enemy_kills", 0.0)), "brk": int(g("black_breakthrough", 0) or 0)}


def run_one(entry, seed):
    log = os.path.join(OUT, "logs", f"{os.path.basename(entry).replace('.py', '')}_s{seed}.log")
    os.makedirs(os.path.dirname(log), exist_ok=True)
    with open(CFG, "w") as f:
        f.write(f"{seed} 10 10 20 0 fixed_frontage 1.0 B3_ADAPTIVE")
    http_get("/stop")
    time.sleep(2)
    env = dict(os.environ)
    env["SCENARIO_SCRIPT"] = "scenario_composition"
    env["LLM_ENABLED"] = "false"
    env["PYTHONUNBUFFERED"] = "1"
    for k in ("W6_ANTI_EVASION", "W6_MODE", "W6_FEATURES", "W6_ISO", "W6_SHADOW_ONLY"):
        env.pop(k, None)
    from maritime_metrics import GameMetricsCollector
    coll = GameMetricsCollector(); coll.start()
    t0 = time.time()
    with open(log, "w") as f:
        subprocess.Popen([PY, entry, "--uavs"], cwd=ROOT, env=env,
                         stdout=f, stderr=subprocess.STDOUT).wait()
    wall = time.time() - t0
    coll.stop()
    text = open(log, encoding="utf-8", errors="replace").read()
    explored = coll.summary()["total_explored_area_km2"]
    m = parse_meta(text)
    return {"candidate": os.path.basename(entry).replace(".py", ""), "seed": seed,
            "result": m["result"], "clean_win": int(m["result"] == "Result.Victory" and m["brk"] == 0),
            "enemy_kills": m["kills"], "friendly_usv_dead": m["dead"], "breakthrough": m["brk"],
            "explored_area_km2": round(explored, 1), "resolution_time": m["vt"],
            "wall_s": round(wall, 1)}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--entries", nargs="+", required=True)
    ap.add_argument("--seeds", nargs="+", type=int, default=[4001, 4002, 4003])
    ap.add_argument("--label", default="w7_dev")
    args = ap.parse_args()
    path = os.path.join(OUT, "W7_DEV_RESULTS.csv")
    done = set()
    if os.path.exists(path):
        done = {(r["candidate"], int(r["seed"])) for r in csv.DictReader(open(path))}
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        if not os.path.exists(path):
            w.writeheader()
        for entry in args.entries:
            for seed in args.seeds:
                if (os.path.basename(entry).replace(".py", ""), seed) in done:
                    continue
                print(f"[DEV:{args.label}] {os.path.basename(entry)} s{seed} "
                      f"{time.strftime('%H:%M:%S')}", flush=True)
                r = run_one(entry, seed)
                w.writerow({k: r.get(k) for k in COLS})
                print(f"   -> {r['result']} clean={r['clean_win']} dead={r['friendly_usv_dead']} "
                      f"brk={r['breakthrough']}", flush=True)
    print("[done]")


if __name__ == "__main__":
    sys.exit(main())
