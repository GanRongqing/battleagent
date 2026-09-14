#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""run_variable_cardinality_eval.py — V5 variable-cardinality × random-trajectory 评估

每局：
  1. 写 composition 配置文件（RW_CFG_FILE）：seed w_usv w_uav b_usv b_uav frontage_mode
  2. 运行 V5 agent（SCENARIO_SCRIPT=scenario_composition，黑方 USV 随机航路）
  3. 解析 META + 结果 → 记录 composition / engine / clean / 战术 / commander 指标

用法:
  python run_variable_cardinality_eval.py --dev            # DEV compositions
  python run_variable_cardinality_eval.py --final          # FINAL compositions
  python run_variable_cardinality_eval.py --seeds 1 2 3 --comp 5 5 5 5
"""
import os
import re
import csv
import time
import subprocess

ROOT = "/root/autodl-tmp/hsystem"
PY = "/root/miniconda3/envs/hsystem_env/bin/python"
CSV_PATH = os.path.join(ROOT, "variable_cardinality_results.csv")
LOG_DIR = os.path.join(ROOT, "logs_vc")
CFG_FILE = os.getenv("RW_CFG_FILE", "/tmp/opencode/rw_cfg.txt")
SCENARIO = "scenario_composition"
DEFAULT_AGENT = os.path.join(ROOT, "agent_hybrid_v5.py")
API = "http://127.0.0.1:8000"

FRONTAGE = "fixed_frontage"   # 主实验：固定 60km 正面，数量→密度增大

# DEV compositions（对称，覆盖小/中/大 + 不同 USV/UAV 比）
DEV_COMPOSITIONS = [
    ("C1", 3, 3, 3, 3),
    ("C2", 5, 5, 5, 5),
    ("C3", 7, 4, 7, 4),
    ("C4", 8, 7, 8, 7),
    ("C5", 10, 5, 10, 5),
    ("C6", 10, 10, 10, 10),
    ("C7", 12, 8, 12, 8),
    ("C8", 15, 15, 15, 15),
]
DEV_SEEDS = [1, 2]

# FINAL compositions（unseen，combat-heavy / recon-heavy / balanced / small / medium / large）
FINAL_COMPOSITIONS = [
    ("F1", 4, 4, 4, 4),
    ("F2", 6, 3, 6, 3),
    ("F3", 6, 6, 6, 6),
    ("F4", 7, 7, 7, 7),
    ("F5", 8, 3, 8, 3),
    ("F6", 9, 6, 9, 6),
    ("F7", 10, 3, 10, 3),
    ("F8", 11, 9, 11, 9),
    ("F9", 12, 4, 12, 4),
    ("F10", 13, 10, 13, 10),
    ("F11", 14, 6, 14, 6),
    ("F12", 15, 8, 15, 8),
]
FINAL_SEEDS = [201, 202, 203]   # 3 seeds / composition（36 局 first pass）

COLUMNS = ["composition", "white_usv", "white_uav", "black_usv", "black_uav",
           "frontage", "seed", "engine_result", "clean_result",
           "enemy_usv_kills", "friendly_usv_losses", "friendly_uav_losses",
           "black_breakthrough",
           "first_detection_time", "first_lock_time", "first_kill_time",
           "reacquire_attempts", "reacquire_success",
           "global_reacquire_entries", "global_reacquire_success",
           "coverage_collapse_events", "active_clusters_max",
           "sensor_assisted_locks", "low_conf_commitments",
           "commander_source", "commander_calls", "commander_changes",
           "commander_policy_failures", "commander_api_failures",
           "LLM_avg_latency", "sim_time", "wall_clock_time", "notes"]


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


def write_cfg(seed, wu, wuv, bu, buv, frontage):
    os.makedirs(os.path.dirname(CFG_FILE), exist_ok=True)
    with open(CFG_FILE, "w", encoding="utf-8") as f:
        f.write(f"{seed} {wu} {wuv} {bu} {buv} {frontage}")


def stop_sim():
    try:
        http_get("/stop")
    except Exception:
        pass
    time.sleep(2)


def run_game(comp, wu, wuv, bu, buv, seed, agent_path=DEFAULT_AGENT, llm_enabled=True):
    logfile = os.path.join(LOG_DIR, f"{comp}_seed{seed}.log")
    os.makedirs(LOG_DIR, exist_ok=True)
    write_cfg(seed, wu, wuv, bu, buv, FRONTAGE)
    stop_sim()
    if llm_enabled:
        ensure_api_key()
    env = dict(os.environ)
    env["SCENARIO_SCRIPT"] = SCENARIO
    env["LLM_ENABLED"] = "true" if llm_enabled else "false"
    env["PYTHONUNBUFFERED"] = "1"
    t0 = time.time()
    proc = subprocess.Popen([PY, agent_path, "--uavs"], cwd=ROOT, env=env,
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

    if engine_result == "Result.Victory":
        clean = "quirk_victory" if (brk or 0) > 0 else "clean_victory"
    elif engine_result == "Result.Defeat":
        clean = "clean_defeat"
    else:
        clean = "unfinished"

    notes = ""
    if rc != 0 and engine_result in (None, "UNFINISHED"):
        notes = f"agent_rc={rc}"
    if "Traceback" in text:
        notes += (" traceback" if notes else "traceback")

    return {
        "composition": comp, "white_usv": wu, "white_uav": wuv,
        "black_usv": bu, "black_uav": buv, "frontage": FRONTAGE, "seed": seed,
        "engine_result": engine_result, "clean_result": clean,
        "enemy_usv_kills": mf("enemy_kills"),
        "friendly_usv_losses": mf("friendly_usv_losses"),
        "friendly_uav_losses": uav_loss,
        "black_breakthrough": brk,
        "first_detection_time": mf("first_detection"),
        "first_lock_time": mf("first_lock"),
        "first_kill_time": mf("first_kill"),
        "reacquire_attempts": mf("reacquire_attempts"),
        "reacquire_success": mf("reacquire_success"),
        "global_reacquire_entries": mf("global_reacquire_entries"),
        "global_reacquire_success": mf("global_reacquire_success"),
        "coverage_collapse_events": mf("coverage_collapse_events"),
        "active_clusters_max": mf("active_clusters_max"),
        "sensor_assisted_locks": mf("sensor_assisted_locks"),
        "low_conf_commitments": mf("low_conf_commitments"),
        "commander_source": meta("commander_source", "n/a"),
        "commander_calls": mf("commander_calls"),
        "commander_changes": mf("commander_changes"),
        "commander_policy_failures": mf("commander_policy_failures"),
        "commander_api_failures": mf("commander_api_failures"),
        "LLM_avg_latency": mf("commander_avg_latency"),
        "sim_time": sim_time, "wall_clock_time": round(wall, 1),
        "notes": notes,
    }


def load_done():
    done = set()
    if os.path.exists(CSV_PATH):
        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                done.add((row["composition"], int(row["seed"])))
    return done


def append_row(row):
    new = not os.path.exists(CSV_PATH)
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        if new:
            w.writeheader()
        w.writerow(row)


def summarize(comps, label):
    rows = []
    if os.path.exists(CSV_PATH):
        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["composition"] in comps:
                    rows.append(r)
    if not rows:
        print(f"[{label}] no rows")
        return
    n = len(rows)
    cv = sum(1 for r in rows if r["clean_result"] == "clean_victory")
    ev = sum(1 for r in rows if r["engine_result"] == "Result.Victory")
    def avg(k):
        v = [float(r[k]) for r in rows if r.get(k) not in (None, "")]
        return f"{sum(v)/len(v):.2f}" if v else "-"
    print(f"=== {label} (n={n}) ===")
    print(f"  engine win {ev}/{n} ({ev/n*100:.0f}%) | clean win {cv}/{n} ({cv/n*100:.0f}%)")
    print(f"  USV loss avg {avg('friendly_usv_losses')} | UAV loss avg {avg('friendly_uav_losses')} "
          f"| brk avg {avg('black_breakthrough')}")
    print(f"  global_reacq {avg('global_reacquire_entries')} entries / {avg('global_reacquire_success')} success "
          f"| reacq {avg('reacquire_success')}/{avg('reacquire_attempts')}")
    # per-composition table
    print("  per-composition:")
    for comp in sorted(set(r["composition"] for r in rows)):
        rr = [r for r in rows if r["composition"] == comp]
        c = sum(1 for r in rr if r["clean_result"] == "clean_victory")
        usv = sum(float(r["friendly_usv_losses"]) for r in rr if r.get("friendly_usv_losses"))
        wu = rr[0]["white_usv"]; wuv = rr[0]["white_uav"]
        print(f"    {comp} (USV{wu}/UAV{wuv}): {c}/{len(rr)} clean, usv_loss_avg={usv/len(rr):.1f}")


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", default=DEFAULT_AGENT)
    ap.add_argument("--dev", action="store_true")
    ap.add_argument("--final", action="store_true")
    ap.add_argument("--comp", type=int, nargs=4, default=None)
    ap.add_argument("--name", default="custom", help="composition id for --comp runs")
    ap.add_argument("--seeds", type=int, nargs="*", default=None)
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--summarize", action="store_true")
    args = ap.parse_args()

    if args.summarize:
        summarize([c[0] for c in DEV_COMPOSITIONS], "DEV")
        summarize([c[0] for c in FINAL_COMPOSITIONS], "FINAL")
        return

    done = load_done()
    _llm = not args.no_llm
    if args.comp:
        comps = [(args.name, *args.comp)]
        seeds = args.seeds or [1]
    elif args.dev:
        comps = DEV_COMPOSITIONS
        seeds = DEV_SEEDS
    elif args.final:
        comps = FINAL_COMPOSITIONS
        seeds = FINAL_SEEDS
    else:
        comps = DEV_COMPOSITIONS
        seeds = DEV_SEEDS

    for cid, wu, wuv, bu, buv in comps:
        for sd in seeds:
            if (cid, sd) in done:
                print(f"[skip] {cid} seed {sd}")
                continue
            print(f"[START] {cid} USV{wu}/UAV{wuv} vs USV{bu}/UAV{buv} seed={sd} "
                  f"llm={_llm} {time.strftime('%H:%M:%S')}", flush=True)
            row = run_game(cid, wu, wuv, bu, buv, sd, args.agent, _llm)
            append_row(row)
            print(f"  -> {row['clean_result']} kills={row['enemy_usv_kills']} "
                  f"usv_loss={row['friendly_usv_losses']} uav_loss={row['friendly_uav_losses']} "
                  f"gr={row['global_reacquire_entries']}/{row['global_reacquire_success']} "
                  f"src={row['commander_source']} wall={row['wall_clock_time']}s {row['notes']}",
                  flush=True)

    summarize([c[0] for c in comps], "RUN")


if __name__ == "__main__":
    main()
