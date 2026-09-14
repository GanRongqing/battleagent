#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""dev3/replay_audit/collect_states.py — run W6-dev3(F) S2 x B3 x 4001-4003 with the
decision-neutral allocator state logger on, to build allocator_states.jsonl.

Sourced config = FULL_DEV3 (all components), legacy execution. Logging is decision-neutral.
"""
import csv
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
OUT = os.path.dirname(os.path.abspath(__file__))
PY = "/root/miniconda3/envs/hsystem_env/bin/python"
CFG = "/tmp/opencode/rw_cfg.txt"
API = "http://127.0.0.1:8000"
STATES = os.path.join(OUT, "allocator_states.jsonl")
SEEDS = [4001, 4002, 4003]


def http_get(path):
    import urllib.request
    try:
        with urllib.request.urlopen(API + path, timeout=6) as r:
            return r.status
    except Exception:
        return None


def run_one(seed):
    log = os.path.join(OUT, "logs", f"S2_FULLDEV3_s{seed}.log")
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
    env["W6_MODE"] = "dev3"        # full dev3 (all components) = variant F
    env["W6_ALLOC_LOG"] = "1"
    env["ALLOC_STATES_PATH"] = STATES
    env["RUN_TAG"] = f"S2_dev3_s{seed}"
    env["RUN_SEED"] = str(seed)
    for p in ("/tmp/opencode/w6_metrics.json", "/tmp/opencode/b3_events.json"):
        if os.path.exists(p):
            os.remove(p)
    with open(log, "w") as f:
        subprocess.Popen([PY, os.path.join(ROOT, "agent_hybrid_w6.py"), "--uavs"],
                         cwd=ROOT, env=env, stdout=f, stderr=subprocess.STDOUT).wait()
    text = open(log, encoding="utf-8", errors="replace").read()
    m = re.search(r"\[META\] result=(\S+) victory_time=(\S+) friendly_usv_losses=(\S+)"
                  r" black_breakthrough=(\S+)", text)
    print(f"s{seed}: {m.groups() if m else 'no-meta'} "
          f"states_in_file={sum(1 for _ in open(STATES)) if os.path.exists(STATES) else 0}",
          flush=True)


def main():
    if os.path.exists(STATES):
        os.remove(STATES)
    for seed in SEEDS:
        run_one(seed)
    print("[done]")


if __name__ == "__main__":
    sys.exit(main())
