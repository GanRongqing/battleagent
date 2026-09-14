#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""w6_anti_evasion/dev3/diag_runner.py — 24-episode diagnostic ablation.

S1 + S2, opponent B3_ADAPTIVE only, DEV seeds 4001-4003 (now diagnostic), 4 variants:
  A W5                (agent_hybrid_v5.py)
  B W6-dev2           (agent_hybrid_w6.py, default dev2 mode)
  C W6-dev3           (W6_MODE=dev3)
  D prediction-only   (W6_MODE=prediction_only)
N = 2 scales x 4 variants x 3 seeds = 24 episodes (HARD CAP).

Per episode it also snapshots the W6 metrics dump + b3 events.
"""
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
OUT = os.path.dirname(os.path.abspath(__file__))
PY = "/root/miniconda3/envs/hsystem_env/bin/python"
CFG = "/tmp/opencode/rw_cfg.txt"
API = "http://127.0.0.1:8000"
SCEN = {"S1": (5, 5, 10), "S2": (10, 10, 20)}
SEEDS = [4001, 4002, 4003]
VARIANTS = [("A_W5", "agent_hybrid_v5.py", None, None),
            ("B_dev2", "agent_hybrid_w6.py", "1", "dev2"),
            ("C_dev3", "agent_hybrid_w6.py", "1", "dev3"),
            ("D_predonly", "agent_hybrid_w6.py", "1", "prediction_only")]

COLS = ["scenario", "variant", "seed", "result", "clean_win", "enemy_kills",
        "friendly_usv_dead", "breakthrough", "explored_area_km2", "resolution_time",
        "assignment_changes", "handoffs", "pursuit_cost_reassignments",
        "defensive_reserve_events", "track_maintenance_events", "high_risk_transitions",
        "legacy_controller_actions", "w6_execution_override_actions"]


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
        if v in (None, "None", ""):
            return d
        return v
    return {"result": g("result", "UNFINISHED"),
            "resolution": float(g("victory_time", 0.0)),
            "enemy_kills": float(g("enemy_kills", 0.0)),
            "usv_dead": float(g("friendly_usv_losses", 0.0)),
            "breakthrough": int(g("black_breakthrough", 0) or 0)}


def run_one(scenario, variant, seed):
    agent_path, we, mode = variant[1], variant[2], variant[3]
    wu, wuv, bu = SCEN[scenario]
    log = os.path.join(OUT, "logs", f"{scenario}_{variant[0]}_s{seed}.log")
    os.makedirs(os.path.dirname(log), exist_ok=True)
    with open(CFG, "w") as f:
        f.write(f"{seed} {wu} {wuv} {bu} 0 fixed_frontage 1.0 B3_ADAPTIVE")
    http_get("/stop")
    time.sleep(2)
    env = dict(os.environ)
    env["SCENARIO_SCRIPT"] = "scenario_composition"
    env["LLM_ENABLED"] = "false"
    env["PYTHONUNBUFFERED"] = "1"
    env.pop("W6_ANTI_EVASION", None)
    env.pop("W6_MODE", None)
    env.pop("W6_FEATURES", None)
    is_w5 = variant[0] == "A_W5"
    if not is_w5:
        env["W6_ANTI_EVASION"] = "1"
        env["W6_MODE"] = mode
    for p in ("/tmp/opencode/w6_metrics.json", "/tmp/opencode/b3_events.json"):
        if os.path.exists(p):
            os.remove(p)
    from maritime_metrics import GameMetricsCollector
    coll = GameMetricsCollector()
    coll.start()
    t0 = time.time()
    with open(log, "w") as f:
        subprocess.Popen([PY, os.path.join(ROOT, agent_path), "--uavs"],
                         cwd=ROOT, env=env, stdout=f, stderr=subprocess.STDOUT).wait()
    wall = time.time() - t0
    coll.stop()
    text = open(log, encoding="utf-8", errors="replace").read()
    explored = coll.summary()["total_explored_area_km2"]
    d = {}
    if not is_w5 and os.path.exists("/tmp/opencode/w6_metrics.json"):
        try:
            d = json.load(open("/tmp/opencode/w6_metrics.json"))
        except Exception:
            d = {}
        try:
            shutil.copy("/tmp/opencode/w6_metrics.json",
                        os.path.join(OUT, "w6_dumps", f"{scenario}_{variant[0]}_s{seed}.json"))
        except Exception:
            pass
    meta = parse_meta(text)
    trace = len(re.findall(r"Traceback", text))
    http_err = len(re.findall(r"\[HTTP\].*异常", text))
    row = {"scenario": scenario, "variant": variant[0], "seed": seed,
           "result": meta["result"],
           "clean_win": int(meta["result"] == "Result.Victory" and meta["breakthrough"] == 0),
           "enemy_kills": meta["enemy_kills"], "friendly_usv_dead": meta["usv_dead"],
           "breakthrough": meta["breakthrough"],
           "explored_area_km2": round(explored, 1), "resolution_time": meta["resolution"],
           "assignment_changes": d.get("unique_intercept_plan_changes", 0),
           "handoffs": d.get("handoff_count", 0),
           "pursuit_cost_reassignments": d.get("dev3_handoffs", d.get("handoff_count", 0)),
           "defensive_reserve_events": d.get("defensive_reserve_events", 0),
           "track_maintenance_events": d.get("track_maintenance_assignments", 0),
           "high_risk_transitions": d.get("unique_high_risk_transitions", 0),
           "legacy_controller_actions": 0, "w6_execution_override_actions": d.get("w6_execution_override_actions", 0),
           "errors": trace + http_err, "wall": round(wall, 1)}
    return row


def main():
    path = os.path.join(OUT, "W6_DEV3_DIAGNOSTIC.csv")
    done = set()
    if os.path.exists(path):
        done = {(r["scenario"], r["variant"], int(r["seed"])) for r in csv.DictReader(open(path))}
    n = 0
    for scenario in ("S1", "S2"):
        for variant in VARIANTS:
            for seed in SEEDS:
                key = (scenario, variant[0], seed)
                if key in done:
                    continue
                print(f"[DIAG] {scenario} {variant[0]} s{seed} {time.strftime('%H:%M:%S')}",
                      flush=True)
                row = run_one(scenario, variant, seed)
                new = not os.path.exists(path)
                with open(path, "a", newline="", encoding="utf-8") as f:
                    w = csv.DictWriter(f, fieldnames=COLS)
                    if new:
                        w.writeheader()
                    w.writerow({k: row.get(k) for k in COLS})
                n += 1
                print(f"   -> {row['result']} clean={row['clean_win']} "
                      f"usv_dead={row['friendly_usv_dead']} brk={row['breakthrough']} "
                      f"err={row['errors']} override={row['w6_execution_override_actions']}",
                      flush=True)
    print("[done] rows:",
          len(list(csv.DictReader(open(path)))) if os.path.exists(path) else 0)


if __name__ == "__main__":
    sys.exit(main())
