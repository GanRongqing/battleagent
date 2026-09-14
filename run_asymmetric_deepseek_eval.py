#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""run_asymmetric_deepseek_eval.py — V5 asymmetric/mixed-cardinality 评估（paired）

实验（固定 V5 冻结版本，仅 evaluator 层）：
  A1/A2: White 5 USV + 5 UAV  vs  Black 8 USV + 7 UAV（Black total 15；White 兵力劣势）
  B1/B2: White 10 USV + 10 UAV vs Black 10 USV + 10 UAV（Black total 20；20v20）
  A: Harness(--no-llm) | A2/B2: Harness+DeepSeek（真实 provider）
  paired seeds：A=301..320，B=401..420（Harness 与 DeepSeek 用完全相同的 seed→同路径）

输出 4 个独立 CSV + 1 个 paired CSV（不覆盖）。
未提供可靠数据的字段记 N/A（不伪造）。

用法:
  python run_asymmetric_deepseek_eval.py --smoke     # 4 variants × 2 seeds = 8 局
  python run_asymmetric_deepseek_eval.py --run-all   # 正式 80 局（可断点续跑）
  python run_asymmetric_deepseek_eval.py --summarize
"""
import os
import re
import csv
import time
import subprocess

ROOT = "/root/autodl-tmp/hsystem"
PY = "/root/miniconda3/envs/hsystem_env/bin/python"
AGENT = os.path.join(ROOT, "agent_hybrid_v5.py")
CFG_FILE = os.getenv("RW_CFG_FILE", "/tmp/opencode/rw_cfg.txt")
SCENARIO = "scenario_composition"
FRONTAGE = "fixed_frontage"
LOG_DIR = os.path.join(ROOT, "logs_asy")
API = "http://127.0.0.1:8000"

# 官方 composition（项目正式定义）：
#   Black total 15 = 8 USV + 7 UAV（scenario_15v15）
#   Black total 20 = 10 USV + 10 UAV（scenario_20v20）
SCENARIOS = {
    "A": {"name": "v5_5p5_vs15", "wu": 5, "wuv": 5, "bu": 8, "buv": 7, "seeds": list(range(301, 321))},
    "B": {"name": "v5_10p10_vs20", "wu": 10, "wuv": 10, "bu": 10, "buv": 10, "seeds": list(range(401, 421))},
}
POLICIES = {"harness": {"llm": False}, "deepseek": {"llm": True}}

COLUMNS = ["scenario_id", "seed", "white_usv", "white_uav", "black_usv", "black_uav",
           "policy_mode", "engine_result", "clean_result", "black_breakthrough_count",
           "enemy_usv_kills", "enemy_uav_losses", "friendly_usv_losses", "friendly_uav_losses",
           "enemy_usv_kill_ratio", "friendly_usv_survival_ratio", "exchange_ratio",
           "first_detection_time", "first_lock_time", "first_kill_time",
           "max_known_tracks", "max_threat_clusters",
           "reacquire_attempts", "reacquire_success",
           "global_reacquire_entries", "global_reacquire_success",
           "coverage_quality_avg", "coverage_collapse_events",
           "low_confidence_commitments", "sensor_assisted_locks", "standoff_engagements",
           "commander_triggers", "commander_calls", "commander_changes", "commander_no_change",
           "commander_source", "api_failures", "parse_failures", "policy_failures",
           "avg_llm_latency", "sim_time", "wall_time", "notes"]


def ensure_api_key():
    if os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return
    try:
        import json
        secrets = json.load(open(os.path.expanduser("~/.cline/data/secrets.json")))
        k = secrets.get("deepSeekApiKey")
        if k:
            os.environ["ANTHROPIC_AUTH_TOKEN"] = k
    except Exception:
        pass


def http_get(path):
    import urllib.request
    try:
        with urllib.request.urlopen(API + path, timeout=8) as r:
            return r.status
    except Exception:
        return None


def write_cfg(seed, wu, wuv, bu, buv):
    os.makedirs(os.path.dirname(CFG_FILE), exist_ok=True)
    with open(CFG_FILE, "w", encoding="utf-8") as f:
        f.write(f"{seed} {wu} {wuv} {bu} {buv} {FRONTAGE}")


def stop_sim():
    try:
        http_get("/stop")
    except Exception:
        pass
    time.sleep(2)


def run_game(sid, wu, wuv, bu, buv, seed, policy):
    logfile = os.path.join(LOG_DIR, f"{sid}_{policy}_s{seed}.log")
    os.makedirs(LOG_DIR, exist_ok=True)
    write_cfg(seed, wu, wuv, bu, buv)
    stop_sim()
    llm = POLICIES[policy]["llm"]
    if llm:
        ensure_api_key()
    env = dict(os.environ)
    env["SCENARIO_SCRIPT"] = SCENARIO
    env["LLM_ENABLED"] = "true" if llm else "false"
    env["PYTHONUNBUFFERED"] = "1"
    t0 = time.time()
    proc = subprocess.Popen([PY, AGENT, "--uavs"], cwd=ROOT, env=env,
                            stdout=open(logfile, "w"), stderr=subprocess.STDOUT)
    rc = proc.wait()
    wall = time.time() - t0
    text = open(logfile, encoding="utf-8", errors="replace").read()

    def meta(key, default=None):
        m = re.search(rf"\[META\].*?\b{key}=([^\s]+)", text)
        return m.group(1) if m else default

    def mf(key):
        v = meta(key)
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    engine_result = meta("result", "UNFINISHED")
    sim_time = mf("victory_time")
    if sim_time is None:
        m = re.findall(r"\[t=([0-9,]+)s\]", text)
        if m:
            sim_time = float(m[-1].replace(",", ""))
    brk = None
    m = re.search(r"突破: (\d+)", text)
    if m:
        brk = float(m.group(1))
    uav_loss = None
    m = re.search(r"UAV损失: (\d+)", text)
    if m:
        uav_loss = float(m.group(1))
    usv_loss = mf("friendly_usv_losses")
    enemy_kills = mf("enemy_kills")

    if engine_result == "Result.Victory":
        clean = "quirk_victory" if (brk or 0) > 0 else "clean_victory"
    elif engine_result == "Result.Defeat":
        clean = "clean_defeat"
    else:
        clean = "unfinished"

    # 从步进日志解析：max_known_tracks、coverage 缺口、standoff、triggers
    max_tracks = 0
    for m in re.finditer(r"TRACKS: vis=(\d+) lost=(\d+)", text):
        max_tracks = max(max_tracks, int(m.group(1)) + int(m.group(2)))
    triggers = len(re.findall(r"\[COMMANDER REQUEST\]", text))

    notes = ""
    if rc != 0 and engine_result in (None, "UNFINISHED"):
        notes = f"agent_rc={rc}"
    if "Traceback" in text:
        notes += (" traceback" if notes else "traceback")

    def ratio3(kills, losses):
        return (f"{kills / losses:.2f}" if losses and kills is not None else "N/A")

    return {
        "scenario_id": sid, "seed": seed, "white_usv": wu, "white_uav": wuv,
        "black_usv": bu, "black_uav": buv, "policy_mode": policy,
        "engine_result": engine_result, "clean_result": clean,
        "black_breakthrough_count": brk,
        "enemy_usv_kills": enemy_kills, "enemy_uav_losses": "N/A",
        "friendly_usv_losses": usv_loss, "friendly_uav_losses": uav_loss,
        "enemy_usv_kill_ratio": (f"{enemy_kills / bu:.2f}" if enemy_kills is not None else "N/A"),
        "friendly_usv_survival_ratio": (f"{(wu - (usv_loss or 0)) / wu:.2f}" if usv_loss is not None else "N/A"),
        "exchange_ratio": ratio3(enemy_kills, usv_loss),
        "first_detection_time": mf("first_detection"),
        "first_lock_time": mf("first_lock"),
        "first_kill_time": mf("first_kill"),
        "max_known_tracks": max_tracks,
        "max_threat_clusters": mf("active_clusters_max"),
        "reacquire_attempts": mf("reacquire_attempts"),
        "reacquire_success": mf("reacquire_success"),
        "global_reacquire_entries": mf("global_reacquire_entries"),
        "global_reacquire_success": mf("global_reacquire_success"),
        "coverage_quality_avg": "N/A",
        "coverage_collapse_events": mf("coverage_collapse_events"),
        "low_confidence_commitments": mf("low_conf_commitments"),
        "sensor_assisted_locks": mf("sensor_assisted_locks"),
        "standoff_engagements": "N/A",
        "commander_triggers": triggers,
        "commander_calls": mf("commander_calls"),
        "commander_changes": mf("commander_changes"),
        "commander_no_change": mf("commander_no_change"),
        "commander_source": meta("commander_source", "n/a"),
        "api_failures": mf("commander_api_failures"),
        "parse_failures": mf("commander_parse_failures"),
        "policy_failures": mf("commander_policy_failures"),
        "avg_llm_latency": mf("commander_avg_latency"),
        "sim_time": sim_time, "wall_time": round(wall, 1), "notes": notes,
    }


def csv_path(sid, policy):
    name = SCENARIOS[sid]["name"]
    return os.path.join(ROOT, f"{name}_{policy}.csv")


def load_done(sid, policy):
    done = set()
    p = csv_path(sid, policy)
    if os.path.exists(p):
        with open(p, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                done.add(int(row["seed"]))
    return done


def append_row(row, sid, policy):
    p = csv_path(sid, policy)
    new = not os.path.exists(p)
    with open(p, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        if new:
            w.writeheader()
        w.writerow(row)


def write_paired():
    pairs = []
    for sid, sc in SCENARIOS.items():
        hp = csv_path(sid, "harness")
        dp = csv_path(sid, "deepseek")
        h = {int(r["seed"]): r for r in csv.DictReader(open(hp))} if os.path.exists(hp) else {}
        d = {int(r["seed"]): r for r in csv.DictReader(open(dp))} if os.path.exists(dp) else {}
        for sd in sc["seeds"]:
            if sd in h and sd in d:
                hc = h[sd]["clean_result"] == "clean_victory"
                dc = d[sd]["clean_result"] == "clean_victory"
                cls = ("both_win" if hc and dc else
                       "harness_only" if hc and not dc else
                       "deepseek_only" if not hc and dc else "both_lose")
                pairs.append({"scenario": sid, "seed": sd,
                              "harness_engine": h[sd]["engine_result"],
                              "harness_clean": h[sd]["clean_result"],
                              "deepseek_engine": d[sd]["engine_result"],
                              "deepseek_clean": d[sd]["clean_result"],
                              "paired_class": cls})
    with open(os.path.join(ROOT, "v5_asymmetric_paired_results.csv"), "w",
              newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["scenario", "seed", "harness_engine",
                                          "harness_clean", "deepseek_engine",
                                          "deepseek_clean", "paired_class"])
        w.writeheader()
        w.writerows(pairs)
    return pairs


def summarize(sid):
    sc = SCENARIOS[sid]
    print(f"\n===== Scenario {sid} — White {sc['wu']}USV+{sc['wuv']}UAV vs "
          f"Black {sc['bu']}USV+{sc['buv']}UAV (Black total {sc['bu'] + sc['buv']}) =====")
    for pol in ("harness", "deepseek"):
        p = csv_path(sid, pol)
        if not os.path.exists(p):
            print(f"  {pol}: no rows"); continue
        rows = list(csv.DictReader(open(p)))
        n = len(rows)
        ev = sum(1 for r in rows if r["engine_result"] == "Result.Victory")
        cv = sum(1 for r in rows if r["clean_result"] == "clean_victory")
        def avg(key):
            v = [float(r[key]) for r in rows if r.get(key) not in (None, "", "N/A")]
            return f"{sum(v)/len(v):.2f}" if v else "-"
        print(f"  {pol}: n={n} engine={ev} clean={cv} ({cv/n*100:.0f}%) | "
              f"usv_loss={avg('friendly_usv_losses')} uav_loss={avg('friendly_uav_losses')} "
              f"exchange={avg('exchange_ratio')} brk_rate={avg('black_breakthrough_count')} "
              f"gr={avg('global_reacquire_entries')}/{avg('global_reacquire_success')}")
    pairs = [p for p in write_paired() if p["scenario"] == sid]
    from collections import Counter
    c = Counter(p["paired_class"] for p in pairs)
    print(f"  Paired: both_win={c.get('both_win',0)} harness_only={c.get('harness_only',0)} "
          f"deepseek_only={c.get('deepseek_only',0)} both_lose={c.get('both_lose',0)}")


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--run-all", action="store_true")
    ap.add_argument("--scenario", choices=["A", "B"], default=None)
    ap.add_argument("--policy", choices=["harness", "deepseek"], default=None)
    ap.add_argument("--seeds", type=int, nargs="*", default=None)
    ap.add_argument("--summarize", action="store_true")
    args = ap.parse_args()

    if args.summarize:
        write_paired()
        summarize("A")
        summarize("B")
        return

    scenarios = ["A", "B"] if args.scenario is None else [args.scenario]
    policies = ["harness", "deepseek"] if args.policy is None else [args.policy]
    seeds_override = args.seeds

    if args.smoke:
        seed_map = {"A": [301, 302], "B": [401, 402]}

    total_start = time.time()
    for sid in scenarios:
        sc = SCENARIOS[sid]
        seeds = seeds_override or (seed_map[sid] if args.smoke else sc["seeds"])
        for pol in policies:
            done = load_done(sid, pol)
            for sd in seeds:
                if sd in done:
                    print(f"[skip] {sid} {pol} s{sd}")
                    continue
                print(f"[START] {sid} {pol} s{sd} "
                      f"White{sc['wu']}+{sc['wuv']} vs Black{sc['bu']}+{sc['buv']} "
                      f"{time.strftime('%H:%M:%S')}", flush=True)
                row = run_game(sid, sc["wu"], sc["wuv"], sc["bu"], sc["buv"], sd, pol)
                append_row(row, sid, pol)
                print(f"  -> {row['clean_result']} kills={row['enemy_usv_kills']} "
                      f"usv_loss={row['friendly_usv_losses']} uav_loss={row['friendly_uav_losses']} "
                      f"src={row['commander_source']} gr={row['global_reacquire_entries']}"
                      f"/{row['global_reacquire_success']} wall={row['wall_time']}s {row['notes']}",
                      flush=True)
    write_paired()
    summarize("A")
    summarize("B")
    print(f"\nTotal elapsed: {(time.time()-total_start)/60:.1f} min")


if __name__ == "__main__":
    main()
