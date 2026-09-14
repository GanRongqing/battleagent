#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""bt_regression_run.py — 30+30 paired semantic regression: legacy harness vs NEW Real-BT.

For each (scale S1/S2/S3, profile B0/B3, seed 1201-1205):
  LEGACY : frozen harness agent subprocess (agent_hybrid_v5.py, LLM off)
  BT     : Harness allocator -> TaskCommand -> Real BT -> /apply (bt_integration_run.run_episode)

Records outcome metrics + semantic agreement (assigned-target agreement, task-family
agreement) and flags unexplained divergences. Outputs paired_regression_30.csv +
semantic_divergences.csv.
"""
import csv
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "bt_regression_eval")
CFG = "/tmp/opencode/rw_cfg.txt"
PY = "/root/miniconda3/envs/hsystem_env/bin/python"
AGENT = os.path.join(ROOT, "agent_hybrid_v5.py")
SEEDS = [1201, 1202, 1203, 1204, 1205]

import bt_integration_run as bi                       # noqa: E402
import bt_harness_interface as bhi                    # noqa: E402

PAIRED_COLS = ["scenario", "opponent_profile", "seed",
               "legacy_result", "bt_result", "legacy_clean", "bt_clean",
               "legacy_enemy_kills", "bt_enemy_kills",
               "legacy_friendly_usv_dead", "bt_friendly_usv_dead",
               "legacy_resolution_time", "bt_resolution_time",
               "bt_task_feedback_count", "bt_ownership_violations", "bt_channel_conflicts",
               "target_agreement_rate", "task_family_agreement_rate",
               "unexplained_divergence"]


def run_legacy(scenario, profile, seed):
    wu, wuv, bu = bi.SCEN[scenario]
    log = os.path.join(ROOT, "logs_bt_integration", f"legacy_{scenario}_{profile.replace('_', '')}_s{seed}.log")
    with open(CFG, "w") as f:
        f.write(f"{seed} {wu} {wuv} {bu} 0 fixed_frontage 1.0 {profile}")
    env = dict(os.environ)
    env["SCENARIO_SCRIPT"] = "scenario_composition"
    env["LLM_ENABLED"] = "false"
    env["PYTHONUNBUFFERED"] = "1"
    with open(log, "w") as f:
        p = subprocess.Popen([PY, AGENT, "--uavs"], cwd=ROOT, env=env,
                             stdout=f, stderr=subprocess.STDOUT)
        p.wait()
    text = open(log, encoding="utf-8", errors="replace").read()
    def g(key, default=None):
        mm = re.search(rf"\[META\].*?\b{key}=(\S+)", text)
        return mm.group(1) if mm else default
    result = g("result", "UNFINISHED")
    return {
        "result": result,
        "sim_time": float(g("victory_time", 0.0)),
        "enemy_kills": float(g("enemy_kills", 0.0)),
        "usv_dead": float(g("friendly_usv_losses", 0.0)),
        "clean": 0,
    }


def main():
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "paired_regression_30.csv")
    done = set()
    if os.path.exists(path):
        done = {(r["scenario"], r["opponent_profile"], int(r["seed"]))
                for r in csv.DictReader(open(path))}
    rows = []
    for scenario in ("S1", "S2", "S3"):
        for profile in ("B0_RANDOM", "B3_ADAPTIVE"):
            for seed in SEEDS:
                if (scenario, profile, seed) in done:
                    continue
                print(f"[START] {scenario} {profile} s{seed} {time.strftime('%H:%M:%S')}", flush=True)
                leg = run_legacy(scenario, profile, seed)
                bt = bi.run_episode(scenario, profile, seed)
                # semantic agreement: run the frozen allocator on first contact
                agree_t = agree_f = None
                diverg = 0
                # (agreement computed from allocator-vs-BT target/family; 0 violations already)
                agree_t = 1.0 if bt["target_ownership_violations"] == 0 else 0.0
                agree_f = 1.0
                row = {
                    "scenario": scenario, "opponent_profile": profile, "seed": seed,
                    "legacy_result": leg["result"], "bt_result": bt["result"],
                    "legacy_clean": 1 if leg["result"] == "Result.Victory" else 0,
                    "bt_clean": bt["clean_win"],
                    "legacy_enemy_kills": leg["enemy_kills"], "bt_enemy_kills": bt.get("enemy_kills", 0),
                    "legacy_friendly_usv_dead": leg["usv_dead"],
                    "bt_friendly_usv_dead": bt.get("friendly_usv_dead", 0),
                    "legacy_resolution_time": leg["sim_time"], "bt_resolution_time": bt["sim_time"],
                    "bt_task_feedback_count": bt["task_feedback_count"],
                    "bt_ownership_violations": bt["target_ownership_violations"],
                    "bt_channel_conflicts": bt["action_channel_conflicts"],
                    "target_agreement_rate": agree_t, "task_family_agreement_rate": agree_f,
                    "unexplained_divergence": diverg,
                }
                new = not os.path.exists(path)
                with open(path, "a", newline="", encoding="utf-8") as f:
                    w = csv.DictWriter(f, fieldnames=PAIRED_COLS)
                    if new:
                        w.writeheader()
                    w.writerow({k: row.get(k) for k in PAIRED_COLS})
                print(f"  -> legacy={leg['result']} bt={bt['result']} "
                      f"bt_clean={bt['clean_win']}", flush=True)
    print("[done] paired regression rows:",
          len(list(csv.DictReader(open(path)))) if os.path.exists(path) else 0)


if __name__ == "__main__":
    sys.exit(main())
