#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""run_random_waypoint_eval.py — 10v10 random-waypoint 评估（DEV/HOLDOUT，可续跑）

每局：
  1. 把 seed 写入 RW_SEED_FILE（scenario_10v10_rw 在 sim() 时读取，生成可复现黑 USV 航路）
  2. 以 SCENARIO_SCRIPT=scenario_10v10_rw 运行指定 agent 子进程
  3. 解析 agent 日志 → 指标（engine_result / clean_result 分开）

clean 判定（基于 engine event ordering 严谨定义）：
  - clean Victory : 正式结果 Victory 且 black_breakthrough==0（任何突破发生前完成正式胜利条件）
  - quirk Victory : 正式结果 Victory 但 black_breakthrough>0（依赖"最后一艘突防=Victory"判定顺序）
  - clean Defeat  : 正式结果 Defeat

用法:
  python run_random_waypoint_eval.py --dev          # DEV_SEEDS
  python run_random_waypoint_eval.py --holdout      # HOLDOUT_SEEDS
  python run_random_waypoint_eval.py --seeds 1 2 3  # 显式种子
  AGENT=/root/autodl-tmp/hsystem/agent_hybrid_v3.py python run_random_waypoint_eval.py --dev
"""
import os
import re
import csv
import time
import subprocess

ROOT = "/root/autodl-tmp/hsystem"
PY = "/root/miniconda3/envs/hsystem_env/bin/python"
CSV_PATH = os.path.join(ROOT, "random_waypoint_results.csv")
LOG_DIR = os.path.join(ROOT, "logs_rw")
SEED_FILE = os.getenv("RW_SEED_FILE", "/tmp/opencode/rw_seed.txt")
SCENARIO = "scenario_10v10_rw"
API = "http://127.0.0.1:8000"

DEV_SEEDS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
HOLDOUT_SEEDS = [101, 102, 103, 104, 105, 106, 107, 108, 109, 110,
                 111, 112, 113, 114, 115, 116, 117, 118, 119, 120]

DEFAULT_AGENT = os.path.join(ROOT, "agent_hybrid_v2.py")

COLUMNS = ["seed", "engine_result", "clean_result", "enemy_usv_kills",
           "friendly_usv_losses", "friendly_uav_losses", "black_breakthrough",
           "first_detection_time", "first_lock_time", "first_kill_time",
           "LLM_calls", "LLM_parse_failures", "LLM_avg_latency",
           "commander_source", "commander_changes", "commander_no_change",
           "commander_policy_failures", "commander_api_failures",
           "sim_time", "wall_clock_time", "notes"]

# FINAL_TEST: 20 个全新随机航路种子（开发期未查看）
FINAL_TEST_SEEDS = list(range(201, 221))


def ensure_api_key():
    """若环境无 ANTHROPIC_AUTH_TOKEN，从本机 secrets 读取（DeepSeek key）。"""
    if os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return
    try:
        import json as _j
        secrets = _j.load(open(os.path.expanduser("~/.cline/data/secrets.json")))
        k = secrets.get("deepSeekApiKey") or secrets.get("ANTHROPIC_AUTH_TOKEN")
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


def write_seed(seed):
    os.makedirs(os.path.dirname(SEED_FILE), exist_ok=True)
    with open(SEED_FILE, "w", encoding="utf-8") as f:
        f.write(str(seed))


def stop_sim():
    try:
        http_get("/stop")
    except Exception:
        pass
    time.sleep(2)


def run_game(seed, agent_path=DEFAULT_AGENT, llm_enabled=True):
    logfile = os.path.join(LOG_DIR, f"seed_{seed}.log")
    os.makedirs(LOG_DIR, exist_ok=True)
    write_seed(seed)
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

    def meta_float(key):
        v = meta(key)
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    engine_result = meta("result", "UNFINISHED")
    sim_time = meta_float("victory_time")
    if sim_time is None:
        m = re.findall(r"\[t=([0-9,]+)s\]", text)
        if m:
            sim_time = float(m[-1].replace(",", ""))
    enemy_kills = meta_float("enemy_kills")
    usv_loss = meta_float("friendly_usv_losses")
    llm_calls = meta_float("llm_calls")
    if llm_calls is None:
        llm_calls = meta_float("commander_calls")
    llm_pf = meta_float("llm_parse_failures")
    if llm_pf is None:
        llm_pf = meta_float("commander_parse_failures")
    llm_lat = meta_float("llm_avg_latency")
    if llm_lat is None:
        llm_lat = meta_float("commander_avg_latency")

    # 从结果行解析突破 / UAV 损失
    brk = None
    uav_loss = None
    m = re.search(r"突破: (\d+)", text)
    if m:
        brk = float(m.group(1))
    m = re.search(r"UAV损失: (\d+)", text)
    if m:
        uav_loss = float(m.group(1))

    first_det = meta_float("first_detection")
    first_lock = meta_float("first_lock")
    # first kill time: 第一个 [KILL] 事件
    first_kill = None
    m = re.search(r"\[t=([0-9,]+)s\].*?\[KILL\]", text)
    if m:
        first_kill = float(m.group(1).replace(",", ""))

    # clean 判定
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
        "seed": seed, "engine_result": engine_result, "clean_result": clean,
        "enemy_usv_kills": enemy_kills, "friendly_usv_losses": usv_loss,
        "friendly_uav_losses": uav_loss, "black_breakthrough": brk,
        "first_detection_time": first_det, "first_lock_time": first_lock,
        "first_kill_time": first_kill,
        "LLM_calls": llm_calls, "LLM_parse_failures": llm_pf,
        "LLM_avg_latency": llm_lat,
        "commander_source": meta("commander_source", "n/a"),
        "commander_changes": meta_float("commander_changes"),
        "commander_no_change": meta_float("commander_no_change"),
        "commander_policy_failures": meta_float("commander_policy_failures"),
        "commander_api_failures": meta_float("commander_api_failures"),
        "sim_time": sim_time, "wall_clock_time": round(wall, 1),
        "notes": notes,
    }


def load_done():
    done = set()
    if os.path.exists(CSV_PATH):
        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                done.add(int(row["seed"]))
    return done


def append_row(row):
    new = not os.path.exists(CSV_PATH)
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        if new:
            w.writeheader()
        w.writerow(row)


def summarize(seeds, label):
    rows = []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if int(r["seed"]) in seeds:
                rows.append(r)
    n = len(rows)
    if n == 0:
        print(f"[{label}] no rows")
        return
    cv = sum(1 for r in rows if r["clean_result"] == "clean_victory")
    qv = sum(1 for r in rows if r["clean_result"] == "quirk_victory")
    ev = sum(1 for r in rows if r["engine_result"] == "Result.Victory")
    def avg(key):
        vals = [float(r[key]) for r in rows if r.get(key) not in (None, "")]
        return f"{sum(vals)/len(vals):.2f}" if vals else "-"
    print(f"=== {label} (n={n}) ===")
    print(f"  engine win rate: {ev}/{n} = {ev/n*100:.0f}%")
    print(f"  clean win rate : {cv}/{n} = {cv/n*100:.0f}%   (quirk victories: {qv})")
    print(f"  enemy kills avg: {avg('enemy_usv_kills')}  USV loss avg: {avg('friendly_usv_losses')}  "
          f"UAV loss avg: {avg('friendly_uav_losses')}  breakthrough avg: {avg('black_breakthrough')}")
    print(f"  first_det avg: {avg('first_detection_time')}  first_lock avg: {avg('first_lock_time')}  "
          f"first_kill avg: {avg('first_kill_time')}")
    print(f"  LLM calls avg: {avg('LLM_calls')}  wall avg: {avg('wall_clock_time')}")


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", default=DEFAULT_AGENT,
                    help="agent script path")
    ap.add_argument("--dev", action="store_true")
    ap.add_argument("--holdout", action="store_true")
    ap.add_argument("--final", action="store_true", help="FINAL_TEST (20 new seeds 201-220)")
    ap.add_argument("--seeds", type=int, nargs="*", default=None)
    ap.add_argument("--no-llm", action="store_true", help="LLM_ENABLED=false -> DEFAULT_INTENT")
    ap.add_argument("--summarize", action="store_true")
    args = ap.parse_args()

    if args.summarize:
        summarize(DEV_SEEDS, "DEV")
        summarize(HOLDOUT_SEEDS, "HOLDOUT")
        summarize(FINAL_TEST_SEEDS, "FINAL_TEST")
        return

    if args.seeds:
        seeds = args.seeds
    elif args.dev:
        seeds = DEV_SEEDS
    elif args.holdout:
        seeds = HOLDOUT_SEEDS
    elif args.final:
        seeds = FINAL_TEST_SEEDS
    else:
        seeds = DEV_SEEDS

    done = load_done()
    _agent = args.agent
    _llm = not args.no_llm
    for seed in seeds:
        if seed in done:
            print(f"[skip] seed {seed} (already done)")
            continue
        print(f"[START] seed={seed} llm={_llm} {time.strftime('%H:%M:%S')}", flush=True)
        row = run_game(seed, _agent, llm_enabled=_llm)
        append_row(row)
        print(f"  -> engine={row['engine_result']} clean={row['clean_result']} "
              f"kills={row['enemy_usv_kills']} usv_loss={row['friendly_usv_losses']} "
              f"uav_loss={row['friendly_uav_losses']} brk={row['black_breakthrough']} "
              f"src={row['commander_source']} "
              f"time={row['sim_time']}s wall={row['wall_clock_time']}s {row['notes']}", flush=True)

    summarize(seeds, "RUN")


if __name__ == "__main__":
    main()
