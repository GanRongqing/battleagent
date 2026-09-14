#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""run_opponent_formal.py — formal B0 vs B3 opponent evaluation.

White is FROZEN (agent_hybrid_v5.py, harness/LLM-off). Black profile selected via the
config file 7th field. Compares B0_RANDOM vs B3_ADAPTIVE on three scales with PAIRED
seeds 1001-1030 (N=30 per setting, 180 episodes total when both columns are present).

The B0 column reuses the frozen formal run (formal_eval_20260825/episode_results.csv)
plus pressure metrics computed from API game logs. The B3 column is produced by this
runner (live pressure metrics + B3 adaptive event counters).

This runner implements the B3 side (and can run B0 seeds too). Resumable per episode.
"""
import argparse
import csv
import json
import math
import os
import re
import subprocess
import sys
import threading
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "opponent_formal_eval")
LOG_DIR = os.path.join(ROOT, "logs_opponent_formal")
PY = "/root/miniconda3/envs/hsystem_env/bin/python"
AGENT = os.path.join(ROOT, "agent_hybrid_v5.py")
CFG = "/tmp/opencode/rw_cfg.txt"
API = "http://127.0.0.1:8000"
BREAK_X = 50000.0
B3_EVENT_FILE = "/tmp/opencode/b3_events.json"

SCENARIOS = {
    "S1": {"friendly_usv": 5, "friendly_uav": 5, "enemy_combat_usv": 10, "enemy_uav": 0},
    "S2": {"friendly_usv": 10, "friendly_uav": 10, "enemy_combat_usv": 20, "enemy_uav": 0},
    "S3": {"friendly_usv": 15, "friendly_uav": 15, "enemy_combat_usv": 30, "enemy_uav": 0},
}
SEEDS = list(range(1001, 1031))
PROFILES = ["B0_RANDOM", "B3_ADAPTIVE"]

COLS = [
    "experiment_id", "scenario", "scale", "opponent_profile", "seed",
    "friendly_usv_initial", "friendly_uav_initial",
    "enemy_combat_usv_initial", "enemy_uav_initial",
    "result", "victory", "clean_win", "failure_reason",
    "sim_time", "wall_time",
    "friendly_usv_alive", "friendly_usv_dead", "friendly_uav_alive", "friendly_uav_dead",
    "friendly_total_dead",
    "enemy_combat_killed_event", "enemy_combat_killed_terminal",
    "enemy_combat_alive_end", "kill_accounting_mismatch",
    "enemy_breakthrough_count", "enemy_oob_count", "timeout",
    "explored_area_km2", "explored_ratio", "usv_explored_area_km2", "uav_explored_area_km2",
    "peak_simultaneous_threat_count", "mean_simultaneous_threat_count",
    "approach_lane_entropy", "active_group_count_mean", "active_group_count_peak",
    "mean_group_spacing_km", "time_to_first_detection", "time_to_first_engagement",
    "time_to_first_kill", "time_to_resolve_all_combat_threats",
    "peak_active_engagements", "mean_active_engagements",
    "peak_uncovered_hostile_tracks", "mean_uncovered_hostile_tracks",
    "time_with_zero_reliable_tracks", "global_reacquire_count",
    "locks_started", "locks_broken", "damage_hits",
    "b3_replan_count", "b3_lane_shift_count", "b3_dispersion_event_count",
    "b3_detected_white_event_count",
    "http_or_trace_errors", "agent_rc",
]

from maritime_metrics import GameMetricsCollector  # noqa: E402
from opponent_smoke import OpponentMetrics          # noqa: E402


def http_get(path, timeout=8):
    import urllib.request
    try:
        with urllib.request.urlopen(API + path, timeout=timeout) as r:
            return r.status
    except Exception:
        return None


def write_cfg(seed, wu, wuv, bu, buv, profile):
    os.makedirs(os.path.dirname(CFG), exist_ok=True)
    with open(CFG, "w", encoding="utf-8") as f:
        f.write(f"{seed} {wu} {wuv} {bu} {buv} fixed_frontage 1.0 {profile}")


def _meta(text):
    m = re.search(r"\[META\] result=(\S+) victory_time=([0-9.]+)", text)
    def g(k):
        mm = re.search(rf"\[META\].*?\b{k}=(\S+)", text)
        return mm.group(1) if mm else None
    return {"result": m.group(1) if m else "UNFINISHED",
            "victory_time": float(m.group(2)) if m and m.group(2) else 0.0,
            "enemy_kills": g("enemy_kills"),
            "friendly_usv_losses": g("friendly_usv_losses"),
            "friendly_uav_losses": g("friendly_uav_losses"),
            "black_breakthrough": g("black_breakthrough"),
            "global_reacquire_entries": g("global_reacquire_entries"),
            "locks_metrics": g("commander_calls")}


def read_b3_events():
    try:
        with open(B3_EVENT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def run_one(experiment_id, scenario_id, profile, seed):
    sc = SCENARIOS[scenario_id]
    wu, wuv, bu, buv = sc["friendly_usv"], sc["friendly_uav"], sc["enemy_combat_usv"], sc["enemy_uav"]
    logfile = os.path.join(LOG_DIR, f"{scenario_id}_{profile}_s{seed}.log")
    os.makedirs(LOG_DIR, exist_ok=True)
    write_cfg(seed, wu, wuv, bu, buv, profile)
    http_get("/stop")
    time.sleep(2)
    coll = GameMetricsCollector()
    opp = OpponentMetrics(enemy_total=bu)
    coll.start(); opp.start()
    env = dict(os.environ)
    env["SCENARIO_SCRIPT"] = "scenario_composition"
    env["LLM_ENABLED"] = "false"
    env["PYTHONUNBUFFERED"] = "1"
    t0 = time.time()
    with open(logfile, "w") as f:
        p = subprocess.Popen([PY, AGENT, "--uavs"], cwd=ROOT, env=env,
                             stdout=f, stderr=subprocess.STDOUT)
        rc = p.wait()
    wall = time.time() - t0
    coll.stop(); opp.stop()
    text = open(logfile, encoding="utf-8", errors="replace").read()
    meta = _meta(text)
    agent_kills = re.findall(r"\[KILL\] (black_usv\S+)", text)
    agent_kills = list(dict.fromkeys(agent_kills))
    fin = coll.finalize(bu=bu, agent_kill_names=agent_kills)
    ek = meta["enemy_kills"]
    if ek is not None:
        ek = int(ek)
        fin["enemy_combat_killed"] = max(0, ek - fin["enemy_breakthrough_events"]
                                         - fin["enemy_out_of_bounds"])
        fin["enemy_survived"] = max(0, bu - ek)
    summ = coll.summary()
    deaths = coll.friendly_deaths()
    usv_dead = sum(1 for d in deaths if d["type"] == "USV" and not d["alive"])
    uav_dead = sum(1 for d in deaths if d["type"] == "UAV" and not d["alive"])
    om = opp.summarize()
    usv_expl = sum(ur["explored_area_km2"] for ur in coll.unit_rows() if ur["unit_type"] == "USV")
    uav_expl = sum(ur["explored_area_km2"] for ur in coll.unit_rows() if ur["unit_type"] == "UAV")
    b3 = read_b3_events() if profile == "B3_ADAPTIVE" else {}
    # timings
    def first_ts(regex):
        m = re.search(regex, text)
        return m.group(1) if m else None
    time_first_det = first_ts(r"first_detection=(\S+)") or (om or {}).get("time_to_first_contact")
    time_first_kill = first_ts(r"first_kill=(\S+)")
    kill_line = next((i for i, l in enumerate(text.splitlines()) if "[KILL]" in l), None)
    if time_first_kill in (None, "None"):
        if kill_line is not None:
            ts = re.findall(r"\[t=([0-9,]+)s\]", "\n".join(text.splitlines()[:kill_line + 1]))
            if ts:
                time_first_kill = ts[-1].replace(",", "")
    time_resolve = round(meta["victory_time"], 1) if meta["victory_time"] else None
    # engagement / locks
    locks_started = sum(len(v) for v in coll.usv_targets.values())
    locks_broken = max(0, locks_started - summ["sum_kill_credit"]
                       - len([1 for c in coll.usv_chain.values()]))
    engine_result = meta["result"]
    timeout = bool(meta["victory_time"] >= 599000.0) or engine_result == "UNFINISHED"
    victory = engine_result == "Result.Victory"
    clean = victory and fin["enemy_breakthrough_events"] == 0
    brk = fin["enemy_breakthrough_events"]
    oob = fin["enemy_out_of_bounds"]
    combat = fin["enemy_combat_killed"]
    alive_end = max(0, bu - combat - oob - brk)
    term_obs = sum(1 for r in fin["enemy_terminal"].values() if r == "combat_killed")
    mismatch = abs(combat - term_obs)

    if not clean:
        if "Traceback" in text or rc != 0:
            fr = "E_runtime_error"
        elif brk > 0:
            fr = "C_breakthrough"
        elif timeout:
            fr = "A_throughput_timeout"
        elif engine_result == "Result.Defeat" and usv_dead >= wu:
            fr = "D_resource_exhaustion"
        elif engine_result == "Result.Defeat":
            fr = "B_lost_track_reacquire"
        else:
            fr = "F_other"
    else:
        fr = "clean"

    om = om or {}
    g_reacq = meta["global_reacquire_entries"]
    row = {
        "experiment_id": experiment_id, "scenario": scenario_id, "scale": scenario_id,
        "opponent_profile": profile, "seed": seed,
        "friendly_usv_initial": wu, "friendly_uav_initial": wuv,
        "enemy_combat_usv_initial": bu, "enemy_uav_initial": buv,
        "result": engine_result, "victory": int(victory), "clean_win": int(clean),
        "failure_reason": fr,
        "sim_time": round(meta["victory_time"], 1), "wall_time": round(wall, 1),
        "friendly_usv_alive": wu - usv_dead, "friendly_usv_dead": usv_dead,
        "friendly_uav_alive": wuv - uav_dead, "friendly_uav_dead": uav_dead,
        "friendly_total_dead": usv_dead + uav_dead,
        "enemy_combat_killed_event": combat, "enemy_combat_killed_terminal": term_obs,
        "enemy_combat_alive_end": alive_end, "kill_accounting_mismatch": mismatch,
        "enemy_breakthrough_count": brk, "enemy_oob_count": oob, "timeout": int(timeout),
        "explored_area_km2": summ["total_explored_area_km2"],
        "explored_ratio": summ["exploration_ratio"],
        "usv_explored_area_km2": round(usv_expl, 1), "uav_explored_area_km2": round(uav_expl, 1),
        "peak_simultaneous_threat_count": om.get("peak_simultaneous_threat_count"),
        "mean_simultaneous_threat_count": om.get("simultaneous_threat_count"),
        "approach_lane_entropy": om.get("approach_lane_entropy"),
        "active_group_count_mean": om.get("number_of_active_groups"),
        "active_group_count_peak": None,
        "mean_group_spacing_km": om.get("mean_group_spacing"),
        "time_to_first_detection": time_first_det,
        "time_to_first_engagement": first_ts(r"first_lock=(\S+)"),
        "time_to_first_kill": time_first_kill,
        "time_to_resolve_all_combat_threats": time_resolve,
        "peak_active_engagements": None, "mean_active_engagements": None,
        "peak_uncovered_hostile_tracks": None, "mean_uncovered_hostile_tracks": None,
        "time_with_zero_reliable_tracks": None,
        "global_reacquire_count": g_reacq,
        "locks_started": locks_started, "locks_broken": locks_broken,
        "damage_hits": summ["sum_damage_hits"],
        "b3_replan_count": b3.get("replan_count", 0),
        "b3_lane_shift_count": b3.get("lane_shift_count", 0),
        "b3_dispersion_event_count": b3.get("dispersion_event_count", 0),
        "b3_detected_white_event_count": b3.get("detected_white_event_count", 0),
        "http_or_trace_errors": len(re.findall(r"\[HTTP\].*异常|Traceback", text)),
        "agent_rc": rc,
    }
    return {k: row.get(k) for k in COLS}


def append_csv(path, row):
    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        if new:
            w.writeheader()
        w.writerow(row)


def load_done():
    p = os.path.join(OUT, "episode_results.csv")
    if not os.path.exists(p):
        return set()
    return {(r["scenario"], r["opponent_profile"], int(r["seed"]))
            for r in csv.DictReader(open(p))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", choices=["S1", "S2", "S3"], default=None)
    ap.add_argument("--profiles", nargs="*", default=None)
    ap.add_argument("--seeds", nargs="*", type=int, default=None)
    ap.add_argument("--experiment-id", default="formal_b0b3")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)
    scenarios = [args.scenario] if args.scenario else ["S1", "S2", "S3"]
    profiles = args.profiles or PROFILES
    seeds = args.seeds or SEEDS
    done = load_done()
    for sid in scenarios:
        for prof in profiles:
            for sd in seeds:
                key = (sid, prof, sd)
                if key in done:
                    continue
                print(f"[START] {sid} {prof} s{sd} {time.strftime('%H:%M:%S')}", flush=True)
                row = run_one(args.experiment_id, sid, prof, sd)
                append_csv(os.path.join(OUT, "episode_results.csv"), row)
                fname = f"{sid.lower()}_{row['friendly_usv_initial']}p{row['friendly_uav_initial']}_vs{row['enemy_combat_usv_initial']}_{'b0' if prof=='B0_RANDOM' else 'b3'}.csv"
                append_csv(os.path.join(OUT, fname), row)
                print(f"  -> {row['result']} clean={row['clean_win']} usv_dead={row['friendly_usv_dead']} "
                      f"kills={row['enemy_combat_killed_event']} peak_sim={row['peak_simultaneous_threat_count']} "
                      f"explored={row['explored_area_km2']} wall={row['wall_time']}s", flush=True)
    print(f"[done] episodes in opponent_formal_eval: {len(load_done())}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
