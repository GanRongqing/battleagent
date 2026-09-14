#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""auto_harness/phase0/code/corpus_runner.py — run frozen W5 on S2xB3 corpus seeds.

Read-only corpus rollout: writes each episode log under auto_harness/phase0/corpus/logs/,
appends AUTO_HARNESS_EPISODES.csv rows, and keeps W5 unchanged. Usage:
  python corpus_runner.py --start 6001 --end 6010
"""
import csv
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
P0 = os.path.join(ROOT, "auto_harness", "phase0")
LOG_DIR = os.path.join(P0, "corpus", "logs")
EPI = os.path.join(P0, "corpus", "AUTO_HARNESS_EPISODES.csv")
PY = "/root/miniconda3/envs/hsystem_env/bin/python"
CFG = "/tmp/opencode/rw_cfg.txt"
API = "http://127.0.0.1:8000"
COLS = ["episode_id", "seed", "scenario", "white_version", "black_profile",
        "outcome", "clean_win", "breakthrough", "friendly_usv_loss", "enemy_kills",
        "resolution_time", "explored_area_km2", "first_detection", "first_lock",
        "first_kill", "reacquire_attempts", "reacquire_success",
        "first_friendly_death_time", "abnormal_error", "trace_path"]


def http_get(path):
    import urllib.request
    try:
        with urllib.request.urlopen(API + path, timeout=6) as r:
            return r.status
    except Exception:
        return None


def meta_of(text):
    d = {}
    for k in ("result", "victory_time", "first_detection", "first_lock", "first_kill",
              "enemy_kills", "friendly_usv_losses", "black_breakthrough",
              "reacquire_attempts", "reacquire_success"):
        m = re.search(rf"\[META\].*?\b{k}=(\S+)", text)
        if m:
            try:
                d[k] = float(m.group(1))
            except Exception:
                d[k] = m.group(1)
    return d


def run_one(seed):
    log = os.path.join(LOG_DIR, f"S2_B3_s{seed}.log")
    os.makedirs(LOG_DIR, exist_ok=True)
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
    with open(log, "w") as f:
        subprocess.Popen([PY, os.path.join(ROOT, "agent_hybrid_v5.py"), "--uavs"],
                         cwd=ROOT, env=env, stdout=f, stderr=subprocess.STDOUT).wait()
    coll.stop()
    text = open(log, encoding="utf-8", errors="replace").read()
    explored = coll.summary()["total_explored_area_km2"]
    abnormal = 1 if "[META]" not in text else 0
    m = meta_of(text)
    outcome = ("DEFEAT" if m.get("result") == "Result.Defeat" else
               "BREAKTHROUGH_WIN" if (m.get("black_breakthrough", 0) or 0) > 0 else "CLEAN_WIN")
    return {"episode_id": f"S2_B3_s{seed}", "seed": seed, "scenario": "S2",
            "white_version": "W5", "black_profile": "B3_ADAPTIVE", "outcome": outcome,
            "clean_win": int(outcome == "CLEAN_WIN"),
            "breakthrough": int(m.get("black_breakthrough", 0) or 0),
            "friendly_usv_loss": int(m.get("friendly_usv_losses", 0) or 0),
            "enemy_kills": int(m.get("enemy_kills", 0) or 0),
            "resolution_time": m.get("victory_time", 0.0),
            "explored_area_km2": round(explored, 1),
            "first_detection": m.get("first_detection"),
            "first_lock": m.get("first_lock"), "first_kill": m.get("first_kill"),
            "reacquire_attempts": int(m.get("reacquire_attempts", 0) or 0),
            "reacquire_success": int(m.get("reacquire_success", 0) or 0),
            "first_friendly_death_time": None, "abnormal_error": abnormal,
            "trace_path": log}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, required=True)
    ap.add_argument("--end", type=int, required=True)
    a = ap.parse_args()
    done = set()
    if os.path.exists(EPI):
        done = {int(r["seed"]) for r in csv.DictReader(open(EPI)) if r["seed"].isdigit()}
    new_file = not os.path.exists(EPI)
    with open(EPI, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        if new_file:
            w.writeheader()
        for seed in range(a.start, a.end + 1):
            if seed in done:
                continue
            print(f"[CORPUS] S2 B3 s{seed} {time.strftime('%H:%M:%S')}", flush=True)
            try:
                r = run_one(seed)
            except Exception as e:
                print(f"   s{seed} abnormal: {e}", flush=True)
                continue
            w.writerow({k: r.get(k) for k in COLS})
            print(f"   -> {r['outcome']} clean={r['clean_win']} loss={r['friendly_usv_loss']} "
                  f"brk={r['breakthrough']}", flush=True)
    print("[done]")


if __name__ == "__main__":
    sys.exit(main())
