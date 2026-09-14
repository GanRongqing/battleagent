#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""run_scale_eval.py — 规模泛化完整评估（10 局/规模 × 4 = 40 局）

同一 agent（agent_hybrid_v2.py）+ 同一 Skill + 同一 Prompt，仅通过
SCENARIO_SCRIPT 环境变量切换场景规模。RNG 自然变化，不重跑失败对局。

输出:
  scale_generalization_results.csv   每局一行
  scale_generalization_aggregate.txt 聚合表
  logs/scale_<scale>_game<i>.log     每局完整日志

可断点续跑：CSV 中已存在的 (scale, game) 会自动跳过。
"""
import os
import re
import sys
import csv
import time
import subprocess
import signal

ROOT = "/root/autodl-tmp/hsystem"
AGENT = os.path.join(ROOT, "agent_hybrid_v2.py")
PY = "/root/miniconda3/envs/hsystem_env/bin/python"
CSV_PATH = os.path.join(ROOT, "scale_generalization_results.csv")
AGG_PATH = os.path.join(ROOT, "scale_generalization_aggregate.txt")
LOG_DIR = os.path.join(ROOT, "logs")
API = "http://127.0.0.1:8000"

SCALES = [
    ("scenario_10v10", 5, 5, 5, 5),
    ("scenario_15v15", 8, 7, 8, 7),
    ("scenario_20v20", 10, 10, 10, 10),
    ("scenario_30v30", 15, 15, 15, 15),
]
GAMES_PER_SCALE = 10

COLUMNS = ["scenario_scale", "game", "white_usv", "white_uav", "black_usv",
           "black_uav", "result", "simulation_time", "wall_clock_time",
           "enemy_kills", "friendly_usv_losses", "friendly_uav_losses",
           "first_detection_time", "first_lock_time", "max_known_tracks",
           "max_simultaneous_engagements", "LLM_calls", "LLM_parse_failures",
           "avg_LLM_latency", "avg_focus_level", "avg_reserve_ratio",
           "intent_changes", "notes"]


def http_get(path):
    import urllib.request
    try:
        with urllib.request.urlopen(API + path, timeout=10) as r:
            return r.status
    except Exception:
        return None


def stop_sim():
    try:
        http_get("/stop")
    except Exception:
        pass
    time.sleep(2)


def run_game(scale, wusv, wuav, busv, buav, game):
    """跑一局，返回指标 dict。不重跑失败局：任何异常都在 notes 中记录。"""
    logfile = os.path.join(LOG_DIR, f"scale_{scale}_game{game}.log")
    stop_sim()
    env = dict(os.environ)
    env["SCENARIO_SCRIPT"] = scale
    env["LLM_ENABLED"] = "true"
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

    def meta_float(key):
        v = meta(key)
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    result = meta("result", "UNFINISHED")
    victory_time = meta_float("victory_time")
    first_det = meta_float("first_detection")
    first_lock = meta_float("first_lock")
    enemy_kills = meta_float("enemy_kills")
    usv_loss = meta_float("friendly_usv_losses")
    llm_calls = meta_float("llm_calls")
    llm_pf = meta_float("llm_parse_failures")
    llm_lat = meta_float("llm_avg_latency")

    # UAV 损失来自 /result 奖励信号 white_uav_killed（agent 打印了对局结果行）
    # agent 结果行格式: "击杀蓝舰: N | 命中: M | 我方USV损失: A | UAV损失: B | 突破: C"
    uav_loss = None
    m = re.search(r"UAV损失: (\d+)", text)
    if m:
        uav_loss = float(m.group(1))

    # 每步采样: 航迹/交战/意图
    max_tracks, max_engaged = 0, 0
    focus_s, ratio_s, n_samp = [], [], 0
    for line in re.finditer(r"\[t=([0-9,]+)s\].*?TRACKS: vis=(\d+) lost=(\d+) engaged=(\d+)"
                            r".*?INTENT: focus=(\d+) ratio=([0-9.]+)", text):
        vis, lost, eng = int(line.group(2)), int(line.group(3)), int(line.group(4))
        max_tracks = max(max_tracks, vis + lost)
        max_engaged = max(max_engaged, eng)
        focus_s.append(float(line.group(5)))
        ratio_s.append(float(line.group(6)))
        n_samp += 1

    intent_changes = len(re.findall(r"\[INTENT APPLIED\]", text))

    # 结果权威值缺失时用最后一步 sim 时间
    sim_time = victory_time
    if sim_time is None:
        m = re.findall(r"\[t=([0-9,]+)s\]", text)
        if m:
            sim_time = float(m[-1].replace(",", ""))

    avg_focus = (sum(focus_s) / len(focus_s)) if focus_s else None
    avg_ratio = (sum(ratio_s) / len(ratio_s)) if ratio_s else None

    # 崩溃/异常检测（非重跑，记录即可）
    notes = ""
    if rc != 0 and result in (None, "UNFINISHED"):
        notes = f"agent_rc={rc}"
    if "Traceback" in text:
        notes += (" traceback" if notes else "traceback")
    if not re.search(r"对局结果:", text):
        notes += (" no_result" if notes else "no_result")

    return {
        "scenario_scale": scale, "game": game,
        "white_usv": wusv, "white_uav": wuav,
        "black_usv": busv, "black_uav": buav,
        "result": result, "simulation_time": sim_time,
        "wall_clock_time": round(wall, 1),
        "enemy_kills": enemy_kills, "friendly_usv_losses": usv_loss,
        "friendly_uav_losses": uav_loss,
        "first_detection_time": first_det, "first_lock_time": first_lock,
        "max_known_tracks": max_tracks,
        "max_simultaneous_engagements": max_engaged,
        "LLM_calls": llm_calls, "LLM_parse_failures": llm_pf,
        "avg_LLM_latency": llm_lat,
        "avg_focus_level": round(avg_focus, 2) if avg_focus else None,
        "avg_reserve_ratio": round(avg_ratio, 3) if avg_ratio else None,
        "intent_changes": intent_changes, "notes": notes,
    }


def load_done():
    done = set()
    if os.path.exists(CSV_PATH):
        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                done.add((row["scenario_scale"], int(row["game"])))
    return done


def append_row(row):
    new = not os.path.exists(CSV_PATH)
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        if new:
            w.writeheader()
        w.writerow(row)


def main():
    os.makedirs(LOG_DIR, exist_ok=True)
    done = load_done()
    summary = []
    for scale, wusv, wuav, busv, buav in SCALES:
        wins = 0
        for g in range(1, GAMES_PER_SCALE + 1):
            if (scale, g) in done:
                print(f"[skip] {scale} game{g} (already done)")
                continue
            print(f"[START] {scale} game{g}/10 ({wusv}USV/{wuav}UAV vs {busv}/{buav}) "
                  f"{time.strftime('%H:%M:%S')}", flush=True)
            row = run_game(scale, wusv, wuav, busv, buav, g)
            append_row(row)
            print(f"  → {row['result']} enemy_kills={row['enemy_kills']} "
                  f"time={row['simulation_time']}s wall={row['wall_clock_time']}s "
                  f"LLM={row['LLM_calls']} {row['notes']}", flush=True)
        # 本规模汇总
        rows = [r for r in csv.DictReader(open(CSV_PATH, encoding="utf-8"))
                if r["scenario_scale"] == scale]
        wins = sum(1 for r in rows if r["result"] == "Result.Victory")
        summary.append((scale, len(rows), wins, rows))
    write_aggregate(summary)
    print("\n=== 40 局评估完成 ===", flush=True)


def write_aggregate(summary):
    lines = ["# Scale Generalization — 聚合表", ""]
    header = ("| Scale | Games | Wins | Win Rate | Avg Enemy Kills | "
              "Avg USV Loss | Avg UAV Loss | Avg Victory Time(s) | "
              "Avg LLM Calls | Avg Wall Clock(s) |")
    lines.append(header)
    lines.append("|---|--|--|--|--|--|--|--|--|--|")
    for scale, n, wins, rows in summary:
        def avg(key):
            vals = [float(r[key]) for r in rows if r.get(key) not in (None, "")]
            return f"{sum(vals)/len(vals):.1f}" if vals else "-"
        def avg_win(key):
            vals = [float(r[key]) for r in rows
                    if r["result"] == "Result.Victory" and r.get(key) not in (None, "")]
            return f"{sum(vals)/len(vals):.1f}" if vals else "-"
        wr = f"{wins/n*100:.0f}%" if n else "-"
        lines.append(f"| {scale} | {n} | {wins} | {wr} | {avg('enemy_kills')} | "
                     f"{avg('friendly_usv_losses')} | {avg('friendly_uav_losses')} | "
                     f"{avg_win('simulation_time')} | {avg('LLM_calls')} | "
                     f"{avg('wall_clock_time')} |")
    open(AGG_PATH, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
