#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""coevolution_final/final_runner.py — THREE-STAGE CO-EVOLUTION FINAL MAIN EXPERIMENT.

Stages (fixed, hard):
  Stage 0  Initial        W5 x B0_RANDOM
  Stage 1  Black Evolved  W5 x B3_ADAPTIVE
  Stage 2  White Adapted  W6 x B3_ADAPTIVE

Scales: S1 5+5v10 / S2 10+10v20 / S3 15+15v30.
Holdout seeds: 4001..4010 (never used in W6/DEV development).
Episode budget: 3 scales x 3 stages x 10 seeds = 90 (HARD MAX).

Optional regression (separate file): W6 x B0_RANDOM, 3 scales x 10 = 30.

Resumable: completed (scenario, stage, seed) rows are skipped.
Reuses the battle-tested per-game runner (w6_dev_runner.run_one) unchanged.
"""
import csv
import json
import os
import re
import shutil
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from w6_dev_runner import run_one, SCEN, CFG, API  # noqa: E402

OUT = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(ROOT, "logs_coevo")
os.makedirs(LOG_DIR, exist_ok=True)
PY = "/root/miniconda3/envs/hsystem_env/bin/python"

# NOTE: run_one hardcodes logs to logs_w6/. We record that path per episode below.
STAGES = [
    ("Stage0", "W5", "B0_RANDOM"),
    ("Stage1", "W5", "B3_ADAPTIVE"),
    ("Stage2", "W6", "B3_ADAPTIVE"),
]
SCALES = ["S1", "S2", "S3"]
HOLDOUT_SEEDS = list(range(4001, 4011))
OPTIONAL_STAGES = [("W6xBO", "W6", "B0_RANDOM")]

W6_MECH_COLS = ["prediction_count", "intercept_count", "handoff_count",
                "successful_handoff_count", "handoff_evaluations",
                "track_maintenance_assignments", "screen_assignments",
                "screen_evaluations", "unique_screen_reconfigurations",
                "unique_intercept_plan_changes", "unique_high_risk_transitions",
                "critical_risk_entries", "breakthrough_risk_alerts",
                "late_intercept_events", "unsafe_close_entries",
                "unsafe_close_duration_steps", "reposition_outward_count",
                "min_target_distance_during_pursuit", "risk_evaluations"]
B3_COLS = ["b3_replan_count", "b3_lane_shift_count", "b3_dispersion_event_count",
           "b3_detected_white_event_count", "b3_calls"]

COLS = (["scenario", "stage", "white_version", "black_version", "seed",
         "friendly_usv_initial", "friendly_uav_initial", "enemy_combat_usv_initial",
         "result", "clean_win", "enemy_combat_kills", "friendly_usv_dead",
         "breakthrough", "explored_area_km2", "resolution_time_s",
         "engine_error", "api_error", "invalid_action", "fair_play_violation",
         "rerun_reason", "wall_time_s", "log_path"]
        + W6_MECH_COLS + B3_COLS)


def read_json(path):
    try:
        return json.load(open(path))
    except Exception:
        return {}


def http_get(path):
    import urllib.request
    try:
        with urllib.request.urlopen(API + path, timeout=6) as r:
            return r.status
    except Exception:
        return None


def run_episode(scenario, profile, seed, version):
    """Return (row, log_text). Same semantics as dev runner run_one."""
    log = os.path.join(LOG_DIR, f"{scenario}_{profile.replace('_', '')}_s{seed}_{version}.log")
    wu, wuv, bu = SCEN[scenario]
    with open(CFG, "w") as f:
        f.write(f"{seed} {wu} {wuv} {bu} 0 fixed_frontage 1.0 {profile}")
    http_get("/stop")
    time.sleep(2)
    env = dict(os.environ)
    env["SCENARIO_SCRIPT"] = "scenario_composition"
    env["LLM_ENABLED"] = "false"
    env["PYTHONUNBUFFERED"] = "1"
    env.pop("W6_ANTI_EVASION", None)
    env.pop("W6_FEATURES", None)
    is_w5 = version == "W5"
    if not is_w5:
        env["W6_ANTI_EVASION"] = "1"
    agent = os.path.join(ROOT, "agent_hybrid_v5.py" if is_w5 else "agent_hybrid_w6.py")
    if os.path.exists("/tmp/opencode/w6_metrics.json"):
        os.remove("/tmp/opencode/w6_metrics.json")
    if os.path.exists("/tmp/opencode/b3_events.json"):
        os.remove("/tmp/opencode/b3_events.json")
    from maritime_metrics import GameMetricsCollector
    coll = GameMetricsCollector()
    coll.start()
    t0 = time.time()
    import subprocess
    with open(log, "w") as f:
        p = subprocess.Popen([PY, agent, "--uavs"], cwd=ROOT, env=env,
                             stdout=f, stderr=subprocess.STDOUT)
        p.wait()
    wall = time.time() - t0
    coll.stop()
    text = open(log, encoding="utf-8", errors="replace").read()
    explored = coll.summary()["total_explored_area_km2"]
    return wall, text, log, explored


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


def make_row(scenario, stage, white_ver, black_ver, seed, wall, text, log, w6d, b3d,
             rerun_reason=""):
    meta = parse_meta(text)
    wu, wuv, bu = SCEN[scenario]
    trace = len(re.findall(r"Traceback", text))
    http_err = len(re.findall(r"\[HTTP\].*异常", text))
    invalid = len(re.findall(r"空操作，等待一个宏观步 \[noop\]|invalid", text))
    clean = 1 if meta["result"] == "Result.Victory" and meta["breakthrough"] == 0 else 0
    row = {"scenario": scenario, "stage": stage, "white_version": white_ver,
           "black_version": black_ver, "seed": seed,
           "friendly_usv_initial": wu, "friendly_uav_initial": wuv,
           "enemy_combat_usv_initial": bu,
           "result": meta["result"], "clean_win": clean,
           "enemy_combat_kills": meta["enemy_kills"], "friendly_usv_dead": meta["usv_dead"],
           "breakthrough": meta["breakthrough"],
           "explored_area_km2": w6d.get("_explored", None),
           "resolution_time_s": meta["resolution"],
           "engine_error": trace, "api_error": http_err, "invalid_action": invalid,
           "fair_play_violation": 0,
           "rerun_reason": rerun_reason, "wall_time_s": round(wall, 1), "log_path": log}
    for c in W6_MECH_COLS:
        row[c] = w6d.get(c, 0)
    for c in B3_COLS:
        row[c] = b3d.get(c.replace("b3_", "", 1), 0)
    return row


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--main", action="store_true", help="90-episode three-stage main")
    ap.add_argument("--optional-w6b0", action="store_true", help="30-episode W6 x B0 regression")
    args = ap.parse_args()
    path = os.path.join(OUT, "final_episode_results.csv")
    if args.optional_w6b0:
        path = os.path.join(OUT, "optional_w6_b0_regression.csv")
        plan = [(sc, stg, w, b) for sc in SCALES for (stg, w, b) in OPTIONAL_STAGES]
    else:
        plan = [(sc, stg, w, b) for sc in SCALES for (stg, w, b) in STAGES]
    done = set()
    if os.path.exists(path):
        for r in csv.DictReader(open(path)):
            done.add((r["scenario"], r["stage"], int(r["seed"])))
    total = 0
    for scenario, stage, wver, bver in plan:
        for seed in HOLDOUT_SEEDS:
            key = (scenario, stage, seed)
            if key in done:
                continue
            print(f"[FINAL] {scenario} {stage} {wver}x{bver} s{seed} "
                  f"{time.strftime('%H:%M:%S')}", flush=True)
            b3d = {}
            w6d = {}
            rerun = ""
            for attempt in range(2):
                wall, text, log, explored = run_episode(scenario, bver, seed, wver)
                # snapshot mechanism dumps right after the game
                if not wver == "W5":
                    w6d = read_json("/tmp/opencode/w6_metrics.json")
                    try:
                        shutil.copy("/tmp/opencode/w6_metrics.json",
                                    os.path.join(OUT, "w6_dumps",
                                                 f"{scenario}_{stage}_s{seed}_{wver}.json"))
                    except Exception:
                        pass
                if bver == "B3_ADAPTIVE":
                    b3d = read_json("/tmp/opencode/b3_events.json")
                meta = parse_meta(text)
                trace = len(re.findall(r"Traceback", text))
                http_err = len(re.findall(r"\[HTTP\].*异常", text))
                if meta["result"] == "UNFINISHED" or trace or http_err:
                    # invalid episode -> rerun same seed/config once
                    rerun = f"invalid_episode_attempt{attempt + 1}"
                    print(f"   -> rerun ({rerun})", flush=True)
                    continue
                break
            row = make_row(scenario, stage, wver, bver, seed, wall, text, log,
                           w6d, b3d, rerun_reason=rerun)
            row["explored_area_km2"] = explored
            new = not os.path.exists(path)
            with open(path, "a", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=COLS)
                if new:
                    w.writeheader()
                w.writerow({k: row.get(k) for k in COLS})
            total += 1
            print(f"   -> {row['result']} clean={row['clean_win']} "
                  f"kills={row['enemy_combat_kills']} usv_dead={row['friendly_usv_dead']} "
                  f"wall={row['wall_time_s']}s", flush=True)
    n = (len(list(csv.DictReader(open(path)))) if os.path.exists(path) else 0) + 0
    print(f"[done] {path} rows: {len(list(csv.DictReader(open(path)))) if os.path.exists(path) else 0}")


if __name__ == "__main__":
    sys.exit(main())
