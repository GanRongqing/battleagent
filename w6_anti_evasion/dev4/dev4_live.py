#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""dev4/dev4_live.py — W6-dev4 live sanity, S2 x B3 x 4001-4003 (3 episodes)."""
import csv
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
OUT = os.path.dirname(os.path.abspath(__file__))
PY = "/root/miniconda3/envs/hsystem_env/bin/python"
CFG = "/tmp/opencode/rw_cfg.txt"
API = "http://127.0.0.1:8000"
SEEDS = [4001, 4002, 4003]
COLS = ["seed", "result", "clean_win", "enemy_kills", "friendly_usv_dead", "breakthrough",
        "explored_area_km2", "resolution_time", "free_pool_mean", "soft_pool_mean",
        "hard_mean", "reserve_mean", "soft_release", "realloc", "reserve_release",
        "assignment_changes", "hard_commit_violations", "execution_override"]


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


def run_one(seed):
    log = os.path.join(OUT, "logs", f"S2_dev4_s{seed}.log")
    os.makedirs(os.path.dirname(log), exist_ok=True)
    with open(CFG, "w") as f:
        f.write(f"{seed} 10 10 20 0 fixed_frontage 1.0 B3_ADAPTIVE")
    http_get("/stop")
    time.sleep(2)
    env = dict(os.environ)
    env["SCENARIO_SCRIPT"] = "scenario_composition"
    env["LLM_ENABLED"] = "false"
    env["PYTHONUNBUFFERED"] = "1"
    for k in ("W6_ANTI_EVASION", "W6_MODE", "W6_FEATURES", "W6_ISO"):
        env.pop(k, None)
    env["W6_ANTI_EVASION"] = "1"
    env["W6_MODE"] = "dev4"
    env["W6_DEV4_LOG"] = "1"
    env["DEV4_EVENTS_PATH"] = os.path.join(OUT, "dev4_events.jsonl")
    env["DEV4_TRAIL_PATH"] = os.path.join(OUT, "dev4_trail.jsonl")
    env["RUN_TAG"] = f"S2_dev4_s{seed}"
    env["RUN_SEED"] = str(seed)
    for p in ("/tmp/opencode/w6_metrics.json", "/tmp/opencode/b3_events.json"):
        if os.path.exists(p):
            os.remove(p)
    from maritime_metrics import GameMetricsCollector
    coll = GameMetricsCollector()
    coll.start()
    t0 = time.time()
    with open(log, "w") as f:
        subprocess.Popen([PY, os.path.join(ROOT, "agent_hybrid_w6.py"), "--uavs"],
                         cwd=ROOT, env=env, stdout=f, stderr=subprocess.STDOUT).wait()
    wall = time.time() - t0
    coll.stop()
    text = open(log, encoding="utf-8", errors="replace").read()
    explored = coll.summary()["total_explored_area_km2"]
    d = {}
    if os.path.exists("/tmp/opencode/w6_metrics.json"):
        try:
            d = json.load(open("/tmp/opencode/w6_metrics.json"))
        except Exception:
            d = {}
    meta = parse_meta(text)
    row = {"seed": seed, "result": meta["result"],
           "clean_win": int(meta["result"] == "Result.Victory" and meta["brk"] == 0),
           "enemy_kills": meta["kills"], "friendly_usv_dead": meta["dead"],
           "breakthrough": meta["brk"], "explored_area_km2": round(explored, 1),
           "resolution_time": meta["vt"],
           "free_pool_mean": round(d.get("dev4_free_pool_sum", 0) / max(1, d.get("dev4_free_pool_n", 1)), 3),
           "soft_pool_mean": 0, "hard_mean": 0,
           "reserve_mean": round(d.get("dev4_free_pool_n", 0) and
                                 d.get("defensive_reserve_events", 0) / max(1, d.get("dev4_free_pool_n", 1)), 3),
           "soft_release": d.get("dev4_soft_release_events", 0),
           "realloc": d.get("dev4_realloc_events", 0),
           "reserve_release": d.get("dev4_reserve_release_events", 0),
           "assignment_changes": d.get("assignment_change_count", 0),
           "hard_commit_violations": d.get("dev4_hard_commit_violations", 0),
           "execution_override": d.get("w6_execution_override_actions", 0)}
    return row


def main():
    for p in (os.path.join(OUT, "dev4_events.jsonl"), os.path.join(OUT, "dev4_trail.jsonl"),
              os.path.join(OUT, "W6_DEV4_LIVE_SANITY.csv")):
        if os.path.exists(p):
            os.remove(p)
    with open(os.path.join(OUT, "W6_DEV4_LIVE_SANITY.csv"), "w", newline="") as f:
        csv.DictWriter(f, fieldnames=COLS).writeheader()
    for seed in SEEDS:
        print(f"[DEV4-LIVE] S2 s{seed} {time.strftime('%H:%M:%S')}", flush=True)
        r = run_one(seed)
        with open(os.path.join(OUT, "W6_DEV4_LIVE_SANITY.csv"), "a", newline="") as f:
            csv.DictWriter(f, fieldnames=COLS).writerow({k: r.get(k) for k in COLS})
        print(f"   -> {r['result']} clean={r['clean_win']} dead={r['friendly_usv_dead']} "
              f"brk={r['breakthrough']} realloc={r['realloc']} soft={r['soft_release']} "
              f"res_rel={r['reserve_release']} override={r['execution_override']}", flush=True)
    print("[done]")


if __name__ == "__main__":
    sys.exit(main())
