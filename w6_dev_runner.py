#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""w6_dev_runner.py — W5 vs W6 DEV evaluation (DEV seeds 2001-2005).

Compares the frozen W5 harness against the W6 anti-evasion harness on DEV seeds
(never the formal 1001-1030). Component sanity = S1 × B0/B3 × 3 seeds; then 3-scale
DEV = S1/S2/S3 × B0/B3 × 5 seeds × W5/W6.

W6 mechanism metrics (handoff/predict/screen/maintenance) are read from the per-game
/tmp/opencode/w6_metrics.json dumped by the W6 agent.
"""
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "w6_anti_evasion", "eval")
CFG = "/tmp/opencode/rw_cfg.txt"
PY = "/root/miniconda3/envs/hsystem_env/bin/python"
V5 = os.path.join(ROOT, "agent_hybrid_v5.py")
V6 = os.path.join(ROOT, "agent_hybrid_w6.py")
API = "http://127.0.0.1:8000"

SCEN = {"S1": (5, 5, 10), "S2": (10, 10, 20), "S3": (15, 15, 30)}
OPP = ["B0_RANDOM", "B3_ADAPTIVE"]
DEV_SEEDS = [2001, 2002, 2003, 2004, 2005]

COLS = ["scenario", "opponent_profile", "seed", "white_version", "result", "clean_win",
        "enemy_kills", "friendly_usv_dead", "explored_area_km2", "resolution_time",
        "breakthrough",
        "prediction_count", "intercept_count", "handoff_count",
        "track_maintenance_assignments", "screen_assignments",
        "breakthrough_risk_alerts", "late_intercept_events",
        "handoff_evaluations", "successful_handoff_count",
        "unique_intercept_plan_changes", "unique_screen_reconfigurations",
        "screen_evaluations", "unique_high_risk_transitions", "critical_risk_entries",
        "risk_evaluations", "unsafe_close_entries", "unsafe_close_duration_steps",
        "reposition_outward_count", "min_target_distance_during_pursuit"]

# ablation variants -> (white_version label, W6_FEATURES env value or None for W5)
ABLATION_VARIANTS = {
    "W5": ("W5", None),
    "W6_FULL": ("W6_FULL",
                "predictive_intercept,pursuit_cost,handoff,uav_track_maintenance,"
                "adaptive_screen,breakthrough_horizon"),
    "W6_NO_PREDICTION": ("W6_NO_PRED",
                         "pursuit_cost,handoff,uav_track_maintenance,"
                         "adaptive_screen,breakthrough_horizon"),
    "W6_NO_SCREEN": ("W6_NO_SCREEN",
                     "predictive_intercept,pursuit_cost,handoff,uav_track_maintenance,"
                     "breakthrough_horizon"),
    "W6_PREDICTION_ONLY": ("W6_PRED_ONLY", "predictive_intercept"),
    "W6_SCREEN_ONLY": ("W6_SCREEN_ONLY", "adaptive_screen"),
    "W6_NO_BREAKTHROUGH_RISK": ("W6_NO_BRK",
                                "predictive_intercept,pursuit_cost,handoff,"
                                "uav_track_maintenance,adaptive_screen"),
    "W6_OVERLAY": ("W6_OVERLAY",   # overlay-only: no re-allocation (frozen base allocator)
                   "predictive_intercept,uav_track_maintenance,adaptive_screen,"
                   "breakthrough_horizon"),
}


def http_get(path, timeout=8):
    import urllib.request
    try:
        with urllib.request.urlopen(API + path, timeout=timeout) as r:
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


def run_one(scenario, profile, seed, version):
    from maritime_metrics import GameMetricsCollector
    wu, wuv, bu = SCEN[scenario]
    log = os.path.join(ROOT, "logs_w6", f"{scenario}_{profile.replace('_', '')}_s{seed}_{version}.log")
    os.makedirs(os.path.dirname(log), exist_ok=True)
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
    # ablation variant mapping
    is_w5 = version in ("W5",) or (version in ABLATION_VARIANTS and ABLATION_VARIANTS[version][1] is None)
    if not is_w5:
        feat = ABLATION_VARIANTS.get(version)
        if feat:
            env["W6_ANTI_EVASION"] = "1"
            if feat[1]:
                env["W6_FEATURES"] = feat[1]
        else:
            env["W6_ANTI_EVASION"] = "1"
    agent = V5 if is_w5 else V6
    if os.path.exists("/tmp/opencode/w6_metrics.json"):
        os.remove("/tmp/opencode/w6_metrics.json")
    coll = GameMetricsCollector()
    coll.start()
    t0 = time.time()
    with open(log, "w") as f:
        p = subprocess.Popen([PY, agent, "--uavs"], cwd=ROOT, env=env,
                             stdout=f, stderr=subprocess.STDOUT)
        p.wait()
    wall = time.time() - t0
    coll.stop()
    text = open(log, encoding="utf-8", errors="replace").read()
    meta = parse_meta(text)
    explored = coll.summary()["total_explored_area_km2"]
    w6 = {}
    if version == "W6" and os.path.exists("/tmp/opencode/w6_metrics.json"):
        try:
            w6 = json.load(open("/tmp/opencode/w6_metrics.json"))
        except Exception:
            w6 = {}
    elif version in ABLATION_VARIANTS and ABLATION_VARIANTS[version][1] is not None:
        # ablation W6 variants also dump metrics
        try:
            w6 = json.load(open("/tmp/opencode/w6_metrics.json"))
        except Exception:
            w6 = {}
    else:
        w6 = {}
    # snapshot the raw per-game dump for mechanism audit
    if (version == "W6" or (version in ABLATION_VARIANTS and ABLATION_VARIANTS.get(version)
                            and ABLATION_VARIANTS[version][1] is not None)) \
            and os.path.exists("/tmp/opencode/w6_metrics.json"):
        try:
            os.makedirs(os.path.join(OUT, "w6_dumps"), exist_ok=True)
            shutil.copy("/tmp/opencode/w6_metrics.json",
                        os.path.join(OUT, "w6_dumps",
                                     f"{scenario}_{profile.replace('_', '')}_s{seed}_{version}.json"))
        except Exception:
            pass
    clean = 1 if meta["result"] == "Result.Victory" and meta["breakthrough"] == 0 else 0
    return {
        "scenario": scenario, "opponent_profile": profile, "seed": seed,
        "white_version": version, "result": meta["result"], "clean_win": clean,
        "enemy_kills": meta["enemy_kills"], "friendly_usv_dead": meta["usv_dead"],
        "explored_area_km2": explored, "resolution_time": meta["resolution"],
        "breakthrough": meta["breakthrough"],
        "prediction_count": w6.get("prediction_count", 0),
        "intercept_count": w6.get("intercept_count", 0),
        "handoff_count": w6.get("handoff_count", 0),
        "track_maintenance_assignments": w6.get("track_maintenance_assignments", 0),
        "screen_assignments": w6.get("screen_assignments", 0),
        "breakthrough_risk_alerts": w6.get("breakthrough_risk_alerts", 0),
        "late_intercept_events": w6.get("late_intercept_events", 0),
        "handoff_evaluations": w6.get("handoff_evaluations", 0),
        "successful_handoff_count": w6.get("successful_handoff_count", 0),
        "unique_intercept_plan_changes": w6.get("unique_intercept_plan_changes", 0),
        "unique_screen_reconfigurations": w6.get("unique_screen_reconfigurations", 0),
        "screen_evaluations": w6.get("screen_evaluations", 0),
        "unique_high_risk_transitions": w6.get("unique_high_risk_transitions", 0),
        "critical_risk_entries": w6.get("critical_risk_entries", 0),
        "risk_evaluations": w6.get("risk_evaluations", 0),
        "unsafe_close_entries": w6.get("unsafe_close_entries", 0),
        "unsafe_close_duration_steps": w6.get("unsafe_close_duration_steps", 0),
        "reposition_outward_count": w6.get("reposition_outward_count", 0),
        "min_target_distance_during_pursuit": w6.get("min_target_distance_during_pursuit", 0),
        "wall": round(wall, 1),
    }


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--sanity", action="store_true", help="S1 B0/B3 seeds 2001-2003 W5/W6")
    ap.add_argument("--dev", action="store_true", help="S1/S2/S3 B0/B3 seeds 2001-2005 W5/W6")
    ap.add_argument("--ablation", action="store_true", help="S1 B0/B3 seeds 2001-2003 all variants")
    ap.add_argument("--seeds", nargs="*", type=int, default=None)
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    if args.ablation:
        path = os.path.join(OUT, "diagnostic_ablation.csv")
        done = set()
        if os.path.exists(path):
            done = {(r["opponent_profile"], int(r["seed"]), r["white_version"])
                    for r in csv.DictReader(open(path))}
        for profile in OPP:
            for seed in DEV_SEEDS[:3]:
                for variant, (label, _feat) in ABLATION_VARIANTS.items():
                    if (profile, seed, label) in done:
                        continue
                    print(f"[START] S1 {profile} s{seed} {label} "
                          f"{time.strftime('%H:%M:%S')}", flush=True)
                    row = run_one("S1", profile, seed, variant)
                    row["white_version"] = label
                    new = not os.path.exists(path)
                    with open(path, "a", newline="", encoding="utf-8") as f:
                        w = csv.DictWriter(f, fieldnames=COLS)
                        if new:
                            w.writeheader()
                        w.writerow({k: row.get(k) for k in COLS})
                    print(f"  -> {row['result']} clean={row['clean_win']} "
                          f"kills={row['enemy_kills']} usv_dead={row['friendly_usv_dead']} "
                          f"wall={row['wall']}s", flush=True)
        print("[done] ablation rows:",
              len(list(csv.DictReader(open(path)))) if os.path.exists(path) else 0)
        return

    path = os.path.join(OUT, ("component_sanity.csv" if args.sanity else "dev_3scale.csv"))
    done = set()
    if os.path.exists(path):
        done = {(r["scenario"], r["opponent_profile"], int(r["seed"]), r["white_version"])
                for r in csv.DictReader(open(path))}
    scenarios = ["S1"] if args.sanity else ["S1", "S2", "S3"]
    seeds = args.seeds or (DEV_SEEDS[:3] if args.sanity else DEV_SEEDS)
    for scenario in scenarios:
        for profile in OPP:
            for seed in seeds:
                for version in ("W5", "W6"):
                    if (scenario, profile, seed, version) in done:
                        continue
                    print(f"[START] {scenario} {profile} s{seed} {version} "
                          f"{time.strftime('%H:%M:%S')}", flush=True)
                    row = run_one(scenario, profile, seed, version)
                    new = not os.path.exists(path)
                    with open(path, "a", newline="", encoding="utf-8") as f:
                        w = csv.DictWriter(f, fieldnames=COLS)
                        if new:
                            w.writeheader()
                        w.writerow({k: row.get(k) for k in COLS})
                    print(f"  -> {row['result']} clean={row['clean_win']} "
                          f"kills={row['enemy_kills']} handoff={row['handoff_count']} "
                          f"wall={row['wall']}s", flush=True)
    print("[done]", path, "rows:",
          len(list(csv.DictReader(open(path)))) if os.path.exists(path) else 0)


if __name__ == "__main__":
    sys.exit(main())
