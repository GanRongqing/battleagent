#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""dev4_soft_shadow_audit/shadow_live.py — live shadow audit episodes.
Real policy = W5 (agent dev4_2 + W6_SHADOW_ONLY=1 => allocator passthrough, no override).
S2 x B3 x 4001-4003, one each. Logs shadow.jsonl only."""
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
OUT = os.path.dirname(os.path.abspath(__file__))
PY = "/root/miniconda3/envs/hsystem_env/bin/python"
CFG = "/tmp/opencode/rw_cfg.txt"
API = "http://127.0.0.1:8000"
SHADOW = os.path.join(OUT, "shadow.jsonl")


def http_get(path):
    import urllib.request
    try:
        with urllib.request.urlopen(API + path, timeout=6) as r:
            return r.status
    except Exception:
        return None


def run_one(seed):
    log = os.path.join(OUT, "logs", f"S2_shadow_s{seed}.log")
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
    env["W6_MODE"] = "dev4_2"
    env["W6_SHADOW_ONLY"] = "1"
    env["SHADOW_PATH"] = SHADOW
    env["RUN_TAG"] = f"S2_shadow_s{seed}"
    env["RUN_SEED"] = str(seed)
    t0 = time.time()
    with open(log, "w") as f:
        subprocess.Popen([PY, os.path.join(ROOT, "agent_hybrid_w6.py"), "--uavs"],
                         cwd=ROOT, env=env, stdout=f, stderr=subprocess.STDOUT).wait()
    wall = time.time() - t0
    print(f"s{seed} wall={wall:.0f}s shadow_lines="
          f"{sum(1 for _ in open(SHADOW)) if os.path.exists(SHADOW) else 0}", flush=True)


def main():
    if os.path.exists(SHADOW):
        os.remove(SHADOW)
    for seed in (4001, 4002, 4003):
        print(f"[SHADOW] S2 s{seed} {time.strftime('%H:%M:%S')}", flush=True)
        run_one(seed)
    print("[done]")


if __name__ == "__main__":
    sys.exit(main())
