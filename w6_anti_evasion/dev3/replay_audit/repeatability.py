#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""dev3/replay_audit/repeatability.py — same-policy repeatability audit.

White W5, S2 10+10 vs 20, B3_ADAPTIVE, seeds 4001 & 4002, 3 repeats each (6 episodes).
Same config every run (same agent/skill/prompt/B3/scenario/seed/controller/physics/LLM=off).
Captures outcome + a coarse allocator/action divergence trace from the game log
(per-logged-step USV-alive tuple + KILL), and the /status 局内时间 progression cadence.
"""
import csv
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
SEEDS = [4001, 4002]
REPEATS = 3


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


def trace_from_log(path):
    """Coarse deterministic trace: per logged step (sim_time, usv-alive tuple, kills)."""
    trace = []
    for line in open(path, encoding="utf-8", errors="replace"):
        m = re.search(r"\[t=([\d,]+)s\] step=(\d+) \|.*?USV: (\d+)/\d+.*?KILL=(\d+)", line)
        if m:
            trace.append((int(m.group(1).replace(",", "")), int(m.group(3)), int(m.group(4))))
    return trace


def run_once(seed, rep):
    log = os.path.join(OUT, "logs", f"W5rep_s{seed}_r{rep}.log")
    os.makedirs(os.path.dirname(log), exist_ok=True)
    with open(CFG, "w") as f:
        f.write(f"{seed} 10 10 20 0 fixed_frontage 1.0 B3_ADAPTIVE")
    http_get("/stop")
    time.sleep(2)
    env = dict(os.environ)
    env["SCENARIO_SCRIPT"] = "scenario_composition"
    env["LLM_ENABLED"] = "false"
    env["PYTHONUNBUFFERED"] = "1"
    env.pop("W6_ANTI_EVASION", None)
    env.pop("W6_MODE", None)
    env.pop("W6_FEATURES", None)
    env.pop("W6_ISO", None)
    t0 = time.time()
    with open(log, "w") as f:
        subprocess.Popen([PY, os.path.join(ROOT, "agent_hybrid_v5.py"), "--uavs"],
                         cwd=ROOT, env=env, stdout=f, stderr=subprocess.STDOUT).wait()
    wall = time.time() - t0
    text = open(log, encoding="utf-8", errors="replace").read()
    meta = parse_meta(text)
    tr = trace_from_log(log)
    return dict(seed=seed, rep=rep, wall=round(wall, 1), **meta, trace=tr)


def main():
    path = os.path.join(OUT, "repeatability_runs.csv")
    runs = []
    for seed in SEEDS:
        for rep in range(1, REPEATS + 1):
            print(f"[REP] W5 s{seed} r{rep} {time.strftime('%H:%M:%S')}", flush=True)
            runs.append(run_once(seed, rep))
            print(f"   -> {runs[-1]['result']} clean_win? dead={runs[-1]['dead']} "
                  f"brk={runs[-1]['brk']} vt={runs[-1]['vt']}", flush=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["seed", "rep", "wall_s", "result", "victory_time", "enemy_kills",
                    "friendly_usv_dead", "breakthrough", "trace_len"])
        for r in runs:
            w.writerow([r["seed"], r["rep"], r["wall"], r["result"], r["vt"],
                        r["kills"], r["dead"], r["brk"], len(r["trace"])])
    # per-seed trace compare
    with open(os.path.join(OUT, "repeatability_trace_compare.csv"), "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["seed", "run1_vs_run2", "run2_vs_run3", "first_div_index_12",
                    "first_div_index_23"])
        for seed in SEEDS:
            trs = [r["trace"] for r in runs if r["seed"] == seed]
            row = [seed]
            for i in range(2):
                a, b = trs[i], trs[i + 1]
                div = next((j for j, (x, y) in enumerate(zip(a, b)) if x[1:] != y[1:]),
                           len(min(a, b)))
                row += ["same" if div == len(min(a, b)) else f"div@{div}", div]
            w.writerow(row)
    print("[done]")


if __name__ == "__main__":
    sys.exit(main())
