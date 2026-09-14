#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""dev3/isolation/iso_runner.py — allocator component isolation (B..F).

S2 x B3_ADAPTIVE x 4001-4003, LEGACY execution, uniform UAV behaviour (track-maint OFF).
Strict cumulative gates via env W6_ISO:
  B = prediction
  C = prediction,risk
  D = prediction,risk,pursuit
  E = prediction,risk,pursuit,handoff
  F = prediction,risk,pursuit,handoff,reserve
Variant A (pure W5) reused from W6_DEV3_DIAGNOSTIC.csv.
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
SEEDS = [4001, 4002, 4003]
ISO = [("B_Prediction", "prediction"),
       ("C_PlusRisk", "prediction,risk"),
       ("D_PlusPursuit", "prediction,risk,pursuit"),
       ("E_PlusHandoff", "prediction,risk,pursuit,handoff"),
       ("F_PlusReserve", "prediction,risk,pursuit,handoff,reserve")]
MECH = ["handoff_evaluations", "handoff_count", "dev3_handoffs",
        "dev3_reinforcement_events", "defensive_reserve_events",
        "track_maintenance_assignments", "unique_high_risk_transitions",
        "w6_execution_override_actions", "assignment_change_count",
        "assignment_lifetime_sum", "assignment_lifetime_n"]
COLS = ["variant", "iso", "seed", "result", "clean_win", "enemy_kills",
        "friendly_usv_dead", "breakthrough", "explored_area_km2", "resolution_time",
        "assignment_lifetime_mean_s"] + MECH


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


def run_one(variant, iso, seed):
    log = os.path.join(OUT, "logs", f"S2_{variant}_s{seed}.log")
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
    env["W6_MODE"] = "dev3"
    env["W6_ISO"] = iso
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
    row = {"variant": variant, "iso": iso, "seed": seed, "result": meta["result"],
           "clean_win": int(meta["result"] == "Result.Victory" and meta["breakthrough"] == 0),
           "enemy_kills": meta["enemy_kills"], "friendly_usv_dead": meta["usv_dead"],
           "breakthrough": meta["breakthrough"], "explored_area_km2": round(explored, 1),
           "resolution_time": meta["resolution"]}
    for c in MECH:
        row[c] = d.get(c, 0)
    if d.get("assignment_lifetime_n"):
        row["assignment_lifetime_mean_s"] = round(
            d["assignment_lifetime_sum"] / d["assignment_lifetime_n"], 1)
    return row


def main():
    path = os.path.join(OUT, "allocator_component_isolation.csv")
    # seed A rows from the dev3 diagnostic (pure W5, exact config)
    if not os.path.exists(path):
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=COLS)
            w.writeheader()
        diag = list(csv.DictReader(open(os.path.join(OUT, "..", "W6_DEV3_DIAGNOSTIC.csv"))))
        for r in diag:
            if r["scenario"] == "S2" and r["variant"] == "A_W5":
                with open(path, "a", newline="", encoding="utf-8") as f:
                    wr = csv.DictWriter(f, fieldnames=COLS)
                    wr.writerow({"variant": "A_W5", "iso": "none", "seed": int(r["seed"]),
                                 "result": r["result"], "clean_win": r["clean_win"],
                                 "enemy_kills": r["enemy_kills"], "friendly_usv_dead": r["friendly_usv_dead"],
                                 "breakthrough": r["breakthrough"], "explored_area_km2": r["explored_area_km2"],
                                 "resolution_time": r["resolution_time"]})
    done = {(r["variant"], int(r["seed"])) for r in csv.DictReader(open(path))}
    for variant, iso in ISO:
        for seed in SEEDS:
            if (variant, seed) in done:
                continue
            print(f"[ISO] {variant} ({iso}) s{seed} {time.strftime('%H:%M:%S')}", flush=True)
            row = run_one(variant, iso, seed)
            with open(path, "a", newline="", encoding="utf-8") as f:
                wr = csv.DictWriter(f, fieldnames=COLS)
                wr.writerow({k: row.get(k) for k in COLS})
            print(f"   -> {row['result']} clean={row['clean_win']} "
                  f"dead={row['friendly_usv_dead']} brk={row['breakthrough']} "
                  f"churn={row.get('assignment_change_count')} "
                  f"lifetime={row.get('assignment_lifetime_mean_s')}", flush=True)
    print("[done] rows:", len(list(csv.DictReader(open(path)))))


if __name__ == "__main__":
    sys.exit(main())
