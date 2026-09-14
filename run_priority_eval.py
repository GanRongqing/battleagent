#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""run_priority_eval.py — 优先级测量评估（instrumented）

功能：
  1. Harness 极限 coarse sweep（White 5+5 / 10+10，黑方 total 15→... balanced split）
  2. 指定两组 paired Harness vs Harness+DeepSeek（5+5 vs15、10+10 vs20，同 seeds）
  3. 每局采集 unit contribution（探索/伤害/击杀/死亡），写入 unit_contribution_results.csv

Agent 冻结：agent_hybrid_v5.py；本脚本只做 evaluator/instrumentation。

用法:
  python run_priority_eval.py --limit-white 5    # 极限 coarse sweep（Harness only）
  python run_priority_eval.py --limit-white 10
  python run_priority_eval.py --paired-scenario A --policy harness
  python run_priority_eval.py --paired-scenario A --policy deepseek
  python run_priority_eval.py --paired-scenario B --policy harness
  python run_priority_eval.py --paired-scenario B --policy deepseek
  python run_priority_eval.py --summarize
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
LOG_DIR = os.path.join(ROOT, "logs_prio")
API = "http://127.0.0.1:8000"

from maritime_metrics import GameMetricsCollector  # noqa: E402

# 官方 composition：Black total 15 = 8 USV + 7 UAV；Black total 20 = 10 + 10
PAIRED = {
    "A": {"wu": 5, "wuv": 5, "bu": 8, "buv": 7, "seeds": list(range(301, 321)),
          "file": "v5_5p5_vs15"},
    "B": {"wu": 10, "wuv": 10, "bu": 10, "buv": 10, "seeds": list(range(401, 421)),
          "file": "v5_10p10_vs20"},
}

# 极限 sweep：balanced split（奇数 total → USV 多 1）
def black_split(total):
    uav = total // 2
    usv = total - uav
    return usv, uav

GAME_COLS = ["scenario", "seed", "oob_multiplier",
             "white_usv", "white_uav", "black_usv", "black_uav",
             "policy", "engine_result", "clean_result",
             "friendly_usv_dead", "friendly_uav_dead", "friendly_total_dead",
             "enemy_combat_killed", "enemy_out_of_bounds", "enemy_breakthrough",
             "enemy_survived", "enemy_unknown", "enemy_total",
             "explored_area_km2", "exploration_ratio", "sum_unit_explored_km2",
             "sum_damage_hits", "sum_kill_credit", "black_hit_reward", "agent_kill_count",
             "agent_enemy_kills",
             "commander_source", "commander_calls",
             "sim_time", "wall_time", "notes"]
UNIT_COLS = ["scenario", "seed", "policy", "oob_multiplier", "unit", "unit_type",
             "explored_area_km2", "first_coverage_area_km2",
             "damage_hits", "kill_credit", "targets_damaged",
             "alive", "death_time", "death_cause"]
OOB_EVENT_COLS = ["scenario", "seed", "oob_multiplier", "unit", "unit_type",
                  "oob_time", "oob_x", "oob_y", "terminal"]
STANDARD = {
    "S10": {"name": "10p10_vs20", "wu": 10, "wuv": 10, "bu": 10, "buv": 10,
            "seeds": list(range(401, 431))},
    "S15": {"name": "15p15_vs30", "wu": 15, "wuv": 15, "bu": 15, "buv": 15,
            "seeds": list(range(501, 521))},
}


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


def write_cfg(seed, wu, wuv, bu, buv, oob=1.0):
    os.makedirs(os.path.dirname(CFG_FILE), exist_ok=True)
    with open(CFG_FILE, "w", encoding="utf-8") as f:
        f.write(f"{seed} {wu} {wuv} {bu} {buv} {FRONTAGE} {oob}")


def stop_sim():
    try:
        http_get("/stop")
    except Exception:
        pass
    time.sleep(2)


def run_one(scenario, wu, wuv, bu, buv, seed, policy, llm, oob=1.0):
    logfile = os.path.join(LOG_DIR, f"{scenario}_{policy}_s{seed}_oob{oob}.log")
    os.makedirs(LOG_DIR, exist_ok=True)
    write_cfg(seed, wu, wuv, bu, buv, oob)
    stop_sim()
    if llm:
        ensure_api_key()
    collector = GameMetricsCollector()
    collector.start()
    env = dict(os.environ)
    env["SCENARIO_SCRIPT"] = SCENARIO
    env["LLM_ENABLED"] = "true" if llm else "false"
    env["PYTHONUNBUFFERED"] = "1"
    t0 = time.time()
    proc = subprocess.Popen([PY, AGENT, "--uavs"], cwd=ROOT, env=env,
                            stdout=open(logfile, "w"), stderr=subprocess.STDOUT)
    rc = proc.wait()
    wall = time.time() - t0
    collector.stop()
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
    if engine_result == "Result.Victory":
        clean = "quirk_victory" if (brk or 0) > 0 else "clean_victory"
    elif engine_result == "Result.Defeat":
        clean = "clean_defeat"
    else:
        clean = "unfinished"

    # agent 日志 [KILL] 名单（用于敌方终局交叉核验）
    agent_kill_names = re.findall(r"\[KILL\] (black_usv\S+)", text)
    agent_kill_names = list(dict.fromkeys(agent_kill_names))

    fin = collector.finalize(bu=bu, agent_kill_names=agent_kill_names)
    # 用 agent /result 权威 black_killed 校正终局（collector 轮询在终局可能滞后一拍）
    agent_enemy_kills = mf("enemy_kills")
    if agent_enemy_kills is not None:
        ek = int(agent_enemy_kills)
        brk = fin["enemy_breakthrough_events"]
        oob = fin["enemy_out_of_bounds"]
        fin["enemy_combat_killed"] = max(0, ek - brk - oob)
        fin["enemy_survived"] = max(0, bu - ek)
        fin["enemy_unknown"] = max(0, bu - fin["enemy_combat_killed"] - oob - brk - fin["enemy_survived"])
    summ = collector.summary()
    notes = ""
    if rc != 0 and engine_result in (None, "UNFINISHED"):
        notes = f"agent_rc={rc}"
    if "Traceback" in text:
        notes += (" traceback" if notes else "traceback")
    # damage reconciliation: sum_damage_hits vs black_hit reward
    black_hit_reward = int(collector.reward.get("black_hit", 0) or 0)

    enemy_total = bu
    row = {
        "scenario": scenario, "seed": seed, "oob_multiplier": oob,
        "white_usv": wu, "white_uav": wuv,
        "black_usv": bu, "black_uav": buv, "policy": policy,
        "engine_result": engine_result, "clean_result": clean,
        "friendly_usv_dead": summ["friendly_usv_dead"],
        "friendly_uav_dead": summ["friendly_uav_dead"],
        "friendly_total_dead": summ["friendly_total_dead"],
        "enemy_combat_killed": fin["enemy_combat_killed"],
        "enemy_out_of_bounds": fin["enemy_out_of_bounds"],
        "enemy_breakthrough": fin["enemy_breakthrough_events"],
        "enemy_survived": fin["enemy_survived"],
        "enemy_unknown": fin["enemy_unknown"],
        "enemy_total": enemy_total,
        "explored_area_km2": summ["total_explored_area_km2"],
        "exploration_ratio": summ["exploration_ratio"],
        "sum_unit_explored_km2": summ["sum_unit_explored_km2"],
        "sum_damage_hits": summ["sum_damage_hits"],
        "sum_kill_credit": summ["sum_kill_credit"],
        "black_hit_reward": black_hit_reward,
        "agent_kill_count": len(agent_kill_names),
        "agent_enemy_kills": agent_enemy_kills,
        "commander_source": meta("commander_source", "n/a"),
        "commander_calls": mf("commander_calls"),
        "sim_time": sim_time, "wall_time": round(wall, 1), "notes": notes,
    }
    # 单位贡献行
    unit_rows = []
    for ur in collector.unit_rows():
        unit_rows.append({"scenario": scenario, "seed": seed, "policy": policy,
                          "oob_multiplier": oob, **ur})
    # OOB 事件行（transition analysis）
    oob_event_rows = []
    for ev in fin.get("oob_events", []):
        oob_event_rows.append({"scenario": scenario, "seed": seed, "oob_multiplier": oob, **ev})
    return row, unit_rows, oob_event_rows


def append_csv(path, rows, cols):
    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        if new:
            w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in cols})


def load_done(path, seed_col="seed"):
    done = set()
    if os.path.exists(path):
        with open(path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                done.add(int(r[seed_col]))
    return done


def summarize_paired():
    print("\n===== PAIRED SUMMARY =====")
    for sid, sc in PAIRED.items():
        print(f"\nScenario {sid}: White {sc['wu']}+{sc['wuv']} vs Black {sc['bu']}+{sc['buv']} "
              f"(total {sc['bu'] + sc['buv']})")
        agg = {}
        for pol in ("harness", "deepseek"):
            path = os.path.join(ROOT, f"{sc['file']}_{pol}.csv")
            if not os.path.exists(path):
                print(f"  {pol}: no data"); continue
            rows = list(csv.DictReader(open(path)))
            n = len(rows)
            cv = sum(1 for r in rows if r["clean_result"] == "clean_victory")
            ev = sum(1 for r in rows if r["engine_result"] == "Result.Victory")
            def avg(k):
                v = [float(r[k]) for r in rows if r.get(k) not in (None, "", "N/A")]
                return f"{sum(v)/len(v):.2f}" if v else "-"
            agg[pol] = rows
            print(f"  {pol}: n={n} clean={cv} ({cv/n*100:.0f}%) engine={ev} | "
                  f"usv_dead={avg('friendly_usv_dead')} uav_dead={avg('friendly_uav_dead')} | "
                  f"enemy_combat={avg('enemy_combat_killed')} enemy_oob={avg('enemy_out_of_bounds')} "
                  f"enemy_brk={avg('enemy_breakthrough')} | "
                  f"explored={avg('explored_area_km2')}km2 ratio={avg('exploration_ratio')} | "
                  f"hits={avg('sum_damage_hits')} kills={avg('sum_kill_credit')}")
        # paired
        h = {int(r["seed"]): r for r in agg.get("harness", [])}
        d = {int(r["seed"]): r for r in agg.get("deepseek", [])}
        from collections import Counter
        c = Counter()
        for sd in sc["seeds"]:
            if sd in h and sd in d:
                hc = h[sd]["clean_result"] == "clean_victory"
                dc = d[sd]["clean_result"] == "clean_victory"
                cls = ("both_win" if hc and dc else "harness_only" if hc else
                       "deepseek_only" if dc else "both_lose")
                c[cls] += 1
        print(f"  Paired: both_win={c.get('both_win',0)} harness_only={c.get('harness_only',0)} "
              f"deepseek_only={c.get('deepseek_only',0)} both_lose={c.get('both_lose',0)}")


def summarize_limit():
    print("\n===== HARNESS LIMIT (per white) =====")
    if not os.path.exists(os.path.join(ROOT, "harness_limit_results.csv")):
        print("  no limit data"); return
    rows = list(csv.DictReader(open(os.path.join(ROOT, "harness_limit_results.csv"))))
    from collections import defaultdict
    bywhite = defaultdict(list)
    for r in rows:
        bywhite[r["white_usv"]].append(r)
    for wusv in sorted(bywhite):
        rr = sorted(bywhite[wusv], key=lambda r: int(r["black_total"]))
        print(f"  White {wusv} USV:")
        for r in rr:
            bt = int(r["black_total"])
            cv = sum(1 for x in bywhite[wusv] if x["black_total"] == str(bt)
                     and x["clean_result"] == "clean_victory")
            cnt = sum(1 for x in bywhite[wusv] if x["black_total"] == str(bt))
            print(f"    black_total={bt} ({r['black_usv']}USV+{r['black_uav']}UAV): "
                  f"clean={cv}/{cnt} ({cv/cnt*100:.0f}%)")


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit-white", type=int, choices=[5, 10], default=None)
    ap.add_argument("--paired-scenario", choices=["A", "B"], default=None)
    ap.add_argument("--policy", choices=["harness", "deepseek"], default=None)
    ap.add_argument("--seeds", type=int, nargs="*", default=None)
    ap.add_argument("--limit-totals", type=int, nargs="*", default=None)
    ap.add_argument("--standard", choices=["S10", "S15"], default=None)
    ap.add_argument("--oob", type=float, default=1.0)
    ap.add_argument("--summarize", action="store_true")
    args = ap.parse_args()

    unit_path = os.path.join(ROOT, "unit_contribution_results.csv")
    oob_event_path = os.path.join(ROOT, "oob_transition_analysis.csv")

    def _write_aux(unit_rows, oob_rows):
        append_csv(unit_path, unit_rows, UNIT_COLS)
        append_csv(oob_event_path, oob_rows, OOB_EVENT_COLS)

    if args.summarize:
        summarize_paired()
        summarize_limit()
        return

    # ── Standard scale samples (Harness only, instrumented) ──
    if args.standard:
        sc = STANDARD[args.standard]
        seeds = args.seeds or sc["seeds"]
        game_path = os.path.join(ROOT, f"standard_{sc['name']}_harness.csv")
        done = set()
        if os.path.exists(game_path):
            done = {(int(r["seed"]), float(r["oob_multiplier"]))
                    for r in csv.DictReader(open(game_path))}
        for sd in seeds:
            if (sd, args.oob) in done:
                print(f"[skip] {args.standard} s{sd} (oob={args.oob})")
                continue
            print(f"[START] STANDARD {args.standard} "
                  f"White{sc['wu']}+{sc['wuv']} vs Black{sc['bu']}+{sc['buv']} "
                  f"oob={args.oob} s{sd} {time.strftime('%H:%M:%S')}", flush=True)
            row, unit_rows, oob_rows = run_one(args.standard, sc["wu"], sc["wuv"],
                                               sc["bu"], sc["buv"], sd, "harness", False,
                                               oob=args.oob)
            append_csv(game_path, [row], GAME_COLS)
            _write_aux(unit_rows, oob_rows)
            print(f"  -> {row['clean_result']} usv_dead={row['friendly_usv_dead']} "
                  f"combat={row['enemy_combat_killed']} oob={row['enemy_out_of_bounds']} "
                  f"explored={row['explored_area_km2']}km2 wall={row['wall_time']}s", flush=True)
        return

    # ── Harness 极限 sweep ──
    if args.limit_white:
        wu, wuv = args.limit_white, args.limit_white
        totals = args.limit_totals or (
            [15, 20, 25, 30, 35] if wu == 5 else [20, 25, 30, 35, 40, 45, 50])
        seeds = args.seeds or [301, 302, 303, 304, 305]
        limit_path = os.path.join(ROOT, "harness_limit_results.csv")
        for bt in totals:
            bu, buv = black_split(bt)
            for sd in seeds:
                key = f"{wu}_{bt}_{sd}_{args.oob}"
                if os.path.exists(limit_path):
                    existing = {f"{r['white_usv']}_{r['black_total']}_{r['seed']}_{r.get('oob_multiplier',1.0)}"
                                for r in csv.DictReader(open(limit_path))}
                    if key in existing:
                        print(f"[skip] limit W{wu} bt{bt} s{sd} oob={args.oob}")
                        continue
                print(f"[START] LIMIT W{wu} vs black_total={bt} ({bu}+{buv}) oob={args.oob} "
                      f"s{sd} {time.strftime('%H:%M:%S')}", flush=True)
                row, unit_rows, oob_rows = run_one(f"L{wu}_{bt}", wu, wuv, bu, buv, sd,
                                                   "harness", False, oob=args.oob)
                row["white_usv"] = wu; row["white_uav"] = wuv
                row["black_total"] = bt
                limit_row = {"white_usv": wu, "white_uav": wuv, "black_usv": bu,
                             "black_uav": buv, "black_total": bt, "seed": sd, **row}
                append_csv(limit_path, [limit_row], list(limit_row.keys()))
                _write_aux(unit_rows, oob_rows)
                print(f"  -> {row['clean_result']} explored={row['explored_area_km2']}km2 "
                      f"enemy_combat={row['enemy_combat_killed']} "
                      f"enemy_oob={row['enemy_out_of_bounds']} "
                      f"friendly_dead={row['friendly_total_dead']} wall={row['wall_time']}s",
                      flush=True)
        summarize_limit()
        return

    # ── Paired ──
    if args.paired_scenario:
        sc = PAIRED[args.paired_scenario]
        policies = [args.policy] if args.policy else ["harness", "deepseek"]
        seeds = args.seeds or sc["seeds"]
        for pol in policies:
            game_path = os.path.join(ROOT, f"{sc['file']}_{pol}.csv")
            done = load_done(game_path)
            for sd in seeds:
                if sd in done:
                    print(f"[skip] {args.paired_scenario} {pol} s{sd}")
                    continue
                llm = (pol == "deepseek")
                print(f"[START] {args.paired_scenario} {pol} s{sd} "
                      f"White{sc['wu']}+{sc['wuv']} vs Black{sc['bu']}+{sc['buv']} "
                      f"{time.strftime('%H:%M:%S')}", flush=True)
                row, unit_rows, oob_rows = run_one(args.paired_scenario, sc["wu"], sc["wuv"],
                                                   sc["bu"], sc["buv"], sd, pol, llm,
                                                   oob=args.oob)
                append_csv(game_path, [row], GAME_COLS)
                _write_aux(unit_rows, oob_rows)
                print(f"  -> {row['clean_result']} usv_dead={row['friendly_usv_dead']} "
                      f"enemy_combat={row['enemy_combat_killed']} "
                      f"enemy_oob={row['enemy_out_of_bounds']} "
                      f"explored={row['explored_area_km2']}km2 "
                      f"src={row['commander_source']} wall={row['wall_time']}s", flush=True)
        summarize_paired()
        return

    ap.print_help()


if __name__ == "__main__":
    main()
