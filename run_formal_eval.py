#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""run_formal_eval.py — formal 3-scale evaluation runner (S1/S2/S3, N=30 each).

Reuses maritime_metrics.GameMetricsCollector (exploration + enemy terminal accounting)
and the standard run_priority_eval single-game pattern. Does NOT modify Agent / Skill /
prompt / simulator. Sequential execution (isolation-safe), resumable per episode.

Frozen config: formal_eval_20260825/config_manifest.json
Outputs:        formal_eval_20260825/{episode_results.csv, s{1,2,3}_*.csv,
               aggregate_results.csv, failure_cases.csv, figures/, FORMAL_EVAL_SUMMARY.md,
               FORMAL_EVAL_FOR_REPORT.md}

Usage:
  python run_formal_eval.py                      # run all scenarios (or skip done)
  python run_formal_eval.py --scenario S1        # run one scenario
  python run_formal_eval.py --seeds 1001 1002    # subset
  python run_formal_eval.py --no-llm             # harness only (default: LLM on)
  python run_formal_eval.py --aggregate          # recompute aggregate/figures/md from CSVs
"""
import argparse
import csv
import json
import math
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "formal_eval_20260825")
FIG = os.path.join(OUT, "figures")
PY = "/root/miniconda3/envs/hsystem_env/bin/python"
AGENT = os.path.join(ROOT, "agent_hybrid_v5.py")
CFG_FILE = "/tmp/opencode/rw_cfg.txt"
LOG_DIR = os.path.join(ROOT, "logs_formal")
API = "http://127.0.0.1:8000"

SCENARIOS = {
    "S1": {"friendly_usv": 5, "friendly_uav": 5, "enemy_combat_usv": 10, "enemy_uav": 0},
    "S2": {"friendly_usv": 10, "friendly_uav": 10, "enemy_combat_usv": 20, "enemy_uav": 0},
    "S3": {"friendly_usv": 15, "friendly_uav": 15, "enemy_combat_usv": 30, "enemy_uav": 0},
}
SEEDS = list(range(1001, 1031))
TIMEOUT_SIM = 599_000.0   # engine set_end_time(600000) minus margin

EPISODE_COLS = [
    "scenario", "seed",
    "result", "clean_win", "victory", "failure_reason",
    "sim_time", "wall_time",
    "friendly_usv_initial", "friendly_uav_initial",
    "friendly_usv_alive", "friendly_uav_alive",
    "friendly_usv_dead", "friendly_uav_dead", "friendly_total_dead",
    "enemy_combat_usv_initial", "enemy_uav_initial",
    "enemy_combat_usv_killed", "enemy_uav_killed",
    "enemy_combat_usv_alive_at_end", "enemy_uav_alive_at_end",
    "enemy_combat_kills_event_based", "enemy_combat_kills_terminal_observed",
    "accounting_mismatch",
    "enemy_breakthrough_count", "enemy_oob_count", "timeout", "remaining_combat_threats",
    "total_explored_area_km2", "explored_ratio",
    "usv_explored_area_km2", "uav_explored_area_km2",
    "damage_hits", "kill_credit", "locks_started", "locks_broken",
    "commander_source", "commander_calls", "commander_parse_failures",
    "commander_api_failures", "commander_policy_failures",
    "http_or_trace_errors", "agent_rc", "initial_observation",
]

from maritime_metrics import GameMetricsCollector  # noqa: E402


def ensure_api_key():
    if os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return
    try:
        secrets = json.load(open(os.path.expanduser("~/.cline/data/secrets.json")))
        k = secrets.get("deepSeekApiKey")
        if k:
            os.environ["ANTHROPIC_AUTH_TOKEN"] = k
    except Exception:
        pass


def http_get(path, timeout=10):
    import urllib.request
    try:
        with urllib.request.urlopen(API + path, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def write_cfg(seed, wu, wuv, bu, buv):
    os.makedirs(os.path.dirname(CFG_FILE), exist_ok=True)
    with open(CFG_FILE, "w", encoding="utf-8") as f:
        f.write(f"{seed} {wu} {wuv} {bu} {buv} fixed_frontage 1.0")


def stop_sim():
    try:
        http_get("/stop", timeout=6)
    except Exception:
        pass
    time.sleep(2)


def _meta(text):
    m = re.search(r"\[META\] result=(\S+)", text)
    result = m.group(1) if m else None
    def g(key):
        mm = re.search(rf"\[META\].*?\b{key}=(\S+)", text)
        return mm.group(1) if mm else None
    return {
        "result": result,
        "victory_time": g("victory_time"),
        "enemy_kills": g("enemy_kills"),
        "friendly_usv_losses": g("friendly_usv_losses"),
        "friendly_uav_losses": g("friendly_uav_losses"),
        "black_breakthrough": g("black_breakthrough"),
        "commander_source": g("commander_source"),
        "commander_calls": g("commander_calls"),
        "commander_parse_failures": g("commander_parse_failures"),
        "commander_api_failures": g("commander_api_failures"),
        "commander_policy_failures": g("commander_policy_failures"),
    }


def run_one(scenario_id, seed, wu, wuv, bu, buv, llm=True):
    logfile = os.path.join(LOG_DIR, f"{scenario_id}_s{seed}.log")
    os.makedirs(LOG_DIR, exist_ok=True)
    write_cfg(seed, wu, wuv, bu, buv)
    stop_sim()
    if llm:
        ensure_api_key()

    collector = GameMetricsCollector()
    collector.start()
    env = dict(os.environ)
    env["SCENARIO_SCRIPT"] = "scenario_composition"
    env["LLM_ENABLED"] = "true" if llm else "false"
    env["PYTHONUNBUFFERED"] = "1"
    env.pop("AUDIT_ENABLED", None)
    t0 = time.time()
    with open(logfile, "w") as f:
        proc = subprocess.Popen([PY, AGENT, "--uavs"], cwd=ROOT, env=env,
                                stdout=f, stderr=subprocess.STDOUT)
        rc = proc.wait()
    wall = time.time() - t0
    collector.stop()
    text = open(logfile, encoding="utf-8", errors="replace").read()
    m = _meta(text)

    # initial legal observation summary (from agent's first logged decision round)
    m1 = re.search(r"\[t=[0-9,]+s\] step=(\d+) \| MISSION=\S+ \| USV: (\d+)/(\d+) \| UAV: (\d+)/(\d+) \|"
                   r" TRACKS: vis=(\d+)", text)
    init_obs = "n/a"
    if m1:
        init_obs = (f"step={m1.group(1)} friendly_usv={m1.group(3)} friendly_uav={m1.group(5)} "
                    f"enemy_tracks_visible={m1.group(6)}")

    def fnum(k, default=0.0):
        try:
            return float(m[k]) if m[k] is not None else default
        except (TypeError, ValueError):
            return default

    engine_result = m["result"] or "UNFINISHED"
    sim_time = fnum("victory_time")
    if sim_time <= 0:
        mm = re.findall(r"\[t=([0-9,]+)s\]", text)
        if mm:
            sim_time = float(mm[-1].replace(",", ""))
    brk_agent = int(fnum("black_breakthrough"))
    reason = ""
    rm = re.search(r"对局结果: (\S+)\s*—\s*(.+)", text)
    if rm:
        reason = rm.group(2).strip()

    # agent kill names (event-based, authoritative)
    agent_kill_names = re.findall(r"\[KILL\] (black_usv\S+)", text)
    agent_kill_names = list(dict.fromkeys(agent_kill_names))
    fin = collector.finalize(bu=bu, agent_kill_names=agent_kill_names)
    # reconcile with agent /result reward (authoritative event count)
    ek = int(fnum("enemy_kills")) if m.get("enemy_kills") is not None else None
    if ek is not None:
        brk = fin["enemy_breakthrough_events"]
        oob = fin["enemy_out_of_bounds"]
        fin["enemy_combat_killed"] = max(0, ek - brk - oob)
        fin["enemy_survived"] = max(0, bu - ek)
        fin["enemy_unknown"] = max(0, bu - fin["enemy_combat_killed"] - oob - brk - fin["enemy_survived"])

    summ = collector.summary()
    deaths = collector.friendly_deaths()
    usv_dead = sum(1 for d in deaths if d["type"] == "USV" and not d["alive"])
    uav_dead = sum(1 for d in deaths if d["type"] == "UAV" and not d["alive"])

    brk_count = fin["enemy_breakthrough_events"]
    oob_count = fin["enemy_out_of_bounds"]
    combat_killed = fin["enemy_combat_killed"]
    survived = fin["enemy_survived"]
    terminal_observed = sum(1 for r in fin["enemy_terminal"].values() if r == "combat_killed")
    mismatch = abs(combat_killed - terminal_observed)
    alive_end = max(0, bu - combat_killed - oob_count - brk_count)

    timeout = bool(sim_time >= TIMEOUT_SIM) or engine_result == "UNFINISHED"
    victory = engine_result == "Result.Victory"
    clean_win = victory and brk_count == 0

    # failure_reason / classification for non-clean
    http_errors = len(re.findall(r"\[HTTP\].*异常|Traceback", text))
    failure_reason = "clean" if clean_win else reason
    if not clean_win:
        if "Traceback" in text or rc != 0:
            failure_reason = "runtime_error"
        elif brk_count > 0:
            failure_reason = "breakthrough"
        elif timeout:
            failure_reason = "timeout"
        elif engine_result == "Result.Defeat" and usv_dead >= wu:
            failure_reason = "resource_exhaustion"
        elif engine_result == "Result.Defeat":
            failure_reason = "lost_track_reacquire"
        else:
            failure_reason = "other"

    # engagement locks (derived from existing collector state, not invasive)
    locks_started = sum(len(v) for v in collector.usv_targets.values())
    kill_credit_total = summ["sum_kill_credit"]
    ongoing = len([1 for c in collector.usv_chain.values() if c["target"] in fin["enemy_terminal"]
                   and fin["enemy_terminal"][c["target"]] == "survived"])
    locks_broken = max(0, locks_started - kill_credit_total - ongoing)

    # usv/uav explored split
    usv_expl = sum(ur["explored_area_km2"] for ur in collector.unit_rows() if ur["unit_type"] == "USV")
    uav_expl = sum(ur["explored_area_km2"] for ur in collector.unit_rows() if ur["unit_type"] == "UAV")

    row = {
        "scenario": scenario_id, "seed": seed,
        "result": engine_result, "clean_win": int(clean_win), "victory": int(victory),
        "failure_reason": failure_reason,
        "sim_time": round(sim_time, 1), "wall_time": round(wall, 1),
        "friendly_usv_initial": wu, "friendly_uav_initial": wuv,
        "friendly_usv_alive": wu - usv_dead, "friendly_uav_alive": wuv - uav_dead,
        "friendly_usv_dead": usv_dead, "friendly_uav_dead": uav_dead,
        "friendly_total_dead": usv_dead + uav_dead,
        "enemy_combat_usv_initial": bu, "enemy_uav_initial": buv,
        "enemy_combat_usv_killed": combat_killed, "enemy_uav_killed": 0,
        "enemy_combat_usv_alive_at_end": alive_end, "enemy_uav_alive_at_end": 0,
        "enemy_combat_kills_event_based": combat_killed,
        "enemy_combat_kills_terminal_observed": terminal_observed,
        "accounting_mismatch": mismatch,
        "enemy_breakthrough_count": brk_count, "enemy_oob_count": oob_count,
        "timeout": int(timeout), "remaining_combat_threats": alive_end,
        "total_explored_area_km2": summ["total_explored_area_km2"],
        "explored_ratio": summ["exploration_ratio"],
        "usv_explored_area_km2": round(usv_expl, 1), "uav_explored_area_km2": round(uav_expl, 1),
        "damage_hits": summ["sum_damage_hits"], "kill_credit": kill_credit_total,
        "locks_started": locks_started, "locks_broken": locks_broken,
        "commander_source": m["commander_source"],
        "commander_calls": m["commander_calls"],
        "commander_parse_failures": m["commander_parse_failures"],
        "commander_api_failures": m["commander_api_failures"],
        "commander_policy_failures": m["commander_policy_failures"],
        "http_or_trace_errors": http_errors, "agent_rc": rc,
    }
    row["initial_observation"] = init_obs
    # ensure all columns present
    return {k: row.get(k) for k in EPISODE_COLS}


def append_csv(path, row):
    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=EPISODE_COLS)
        if new:
            w.writeheader()
        w.writerow(row)


def load_episodes():
    p = os.path.join(OUT, "episode_results.csv")
    if not os.path.exists(p):
        return []
    return list(csv.DictReader(open(p, encoding="utf-8")))


def done_seeds(scenario_id):
    done = set()
    for r in load_episodes():
        if r["scenario"] == scenario_id:
            done.add(int(r["seed"]))
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", choices=["S1", "S2", "S3"], default=None)
    ap.add_argument("--seeds", type=int, nargs="*", default=None)
    ap.add_argument("--no-llm", action="store_true", default=False)
    ap.add_argument("--aggregate", action="store_true")
    args = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    os.makedirs(FIG, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)

    if args.aggregate:
        from formal_aggregate import run
        return run(OUT)

    scenarios = [args.scenario] if args.scenario else ["S1", "S2", "S3"]
    for sid in scenarios:
        sc = SCENARIOS[sid]
        wu, wuv, bu, buv = sc["friendly_usv"], sc["friendly_uav"], sc["enemy_combat_usv"], sc["enemy_uav"]
        seeds = args.seeds or SEEDS
        done = done_seeds(sid)
        for sd in seeds:
            if sd in done:
                print(f"[skip] {sid} s{sd}", flush=True)
                continue
            print(f"[START] {sid} White{wu}+{wuv} vs Black{bu}+{buv} s{sd} "
                  f"{time.strftime('%H:%M:%S')}", flush=True)
            row = run_one(sid, sd, wu, wuv, bu, buv, llm=not args.no_llm)
            append_csv(os.path.join(OUT, "episode_results.csv"), row)
            append_csv(os.path.join(OUT, f"s{sid[1:]}_{wu}usv{wuv}uav_vs{bu}usv.csv"), row)
            print(f"  -> {row['result']} clean={row['clean_win']} usv_dead={row['friendly_usv_dead']} "
                  f"combat={row['enemy_combat_usv_killed']} oob={row['enemy_oob_count']} "
                  f"brk={row['enemy_breakthrough_count']} explored={row['total_explored_area_km2']}km2 "
                  f"wall={row['wall_time']}s", flush=True)

    n_done = len(load_episodes())
    print(f"\n[done] episodes so far: {n_done}/90", flush=True)
    if n_done == 90:
        from formal_aggregate import run as agg_run
        agg_run(OUT)
    else:
        print("[note] aggregate deferred until all 90 episodes are complete "
              "(run: python run_formal_eval.py --aggregate)", flush=True)


if __name__ == "__main__":
    sys.exit(main())
