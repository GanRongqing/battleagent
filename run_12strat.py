#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""run_12strat.py — ACE x 12 strategies x N seeds quick generalization eval.

Groups: OLD_LOCAL B0-B3 (scenario_composition + profile), WAVE1 dispersed/two-wave
(external_dispersed/external_twowave), WAVE2 the 6 plan scenarios.
Metrics from canonical [META]. Deterministic step mode expected ON on the API.
Usage: python run_12strat.py [--seeds 43001,43002] [--port 8000]
"""
import argparse, csv, json, os, re, subprocess, sys, time

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "auto_harness", "combat_exchange", "ace_12strategy_n2")
RAW = os.path.join(OUT, "raw_logs")
PY = "/root/miniconda3/envs/hsystem_env/bin/python"
CFG = "/tmp/opencode/rw_cfg.txt"
SEEDFILE = "/tmp/opencode/seed_w0.txt"

# (group, short_id, registered_name, scenario_name, profile)
STRATS = [
    ("OLD_LOCAL", "B0", "B0_RANDOM", "scenario_composition", "B0_RANDOM"),
    ("OLD_LOCAL", "B1", "B1_MULTI_AXIS", "scenario_composition", "B1_MULTI_AXIS"),
    ("OLD_LOCAL", "B2", "B2_COORDINATED_PRESSURE", "scenario_composition", "B2_COORDINATED_PRESSURE"),
    ("OLD_LOCAL", "B3", "B3_ADAPTIVE", "scenario_composition", "B3_ADAPTIVE"),
    ("WAVE1", "W1-1", "分散式 dispersed", "external_dispersed", ""),
    ("WAVE1", "W1-2", "两波次 two-wave", "external_twowave", ""),
    ("WAVE2", "W2-1", "横向编队-中央汇聚箭头突防", "横向编队-中央汇聚箭头突防", ""),
    ("WAVE2", "W2-2", "菱形编队-接近后扇形展开突防", "菱形编队-接近后扇形展开突防", ""),
    ("WAVE2", "W2-3", "菱形编队-两翼包抄中央突进", "菱形编队-两翼包抄中央突进", ""),
    ("WAVE2", "W2-4", "菱形编队-南北两翼镜像夹击", "菱形编队-南北两翼镜像夹击", ""),
    ("WAVE2", "W2-5", "菱形编队-中央汇聚箭头突防", "菱形编队-中央汇聚箭头突防", ""),
    ("WAVE2", "W2-6", "菱形编队-MUSV外侧绕行SUSV中央收缩", "菱形编队-MUSV外侧绕行SUSV中央收缩", ""),
]
FIELDS = ["Group", "Strategy", "Registered_Name", "Seed", "Valid", "Black_Kills",
          "White_USV_Losses", "White_UAV_Losses", "CER", "Exchange_Result", "Terminal_Result",
          "Sim_Time", "Wall_Time", "ACE_SHA256", "Opponent_SHA256"]
ACE_SHA = "7527253c6d5a4bba198e478a990443354ecf5d8cf4e1c98ace66ce50dc809497"


def write_cfg(seed, profile):
    os.makedirs(os.path.dirname(CFG), exist_ok=True)
    with open(CFG, "w", encoding="utf-8") as f:
        f.write(f"{seed} 20 10 30 0 fixed_frontage 1.0 {profile}")


def meta(text):
    g = lambda k: (re.search(rf"\[META\].*?\b{k}=(\S+)", text) or [None, None])[1] \
        if re.search(rf"\[META\].*?\b{k}=(\S+)", text) else None
    m = re.search(r"\[META\] result=(\S+)", text)
    return {"result": m.group(1) if m else "UNFINISHED",
            "enemy_kills": g("enemy_kills"), "friendly_usv_losses": g("friendly_usv_losses"),
            "friendly_uav_losses": g("friendly_uav_losses")}


def run_one(group, sid, name, scen, profile, seed, port):
    logf = os.path.join(RAW, f"{sid}_seed{seed}.log")
    if profile:
        write_cfg(seed, profile)
    open(SEEDFILE, "w").write(str(seed))
    env = dict(os.environ)
    env["SCENARIO_SCRIPT"] = scen
    env["LLM_ENABLED"] = "false"
    env["PYTHONUNBUFFERED"] = "1"
    if profile:
        env["RW_CFG_FILE"] = CFG
    t0 = time.time()
    with open(logf, "w") as f:
        p = subprocess.Popen([PY, "run_agent_wrapper.py", str(port), "expand"],
                             cwd=ROOT, env=env, stdout=f, stderr=subprocess.STDOUT)
        p.wait()
    wall = round(time.time() - t0, 1)
    text = open(logf, encoding="utf-8", errors="replace").read()
    m = meta(text)
    valid = "[META]" in text
    k = int(m["enemy_kills"]) if m["enemy_kills"] else 0
    l = int(m["friendly_usv_losses"]) if m["friendly_usv_losses"] else 0
    uav = int(m["friendly_uav_losses"]) if m["friendly_uav_losses"] else 0
    simt = ""
    for ln in text.splitlines()[::-1]:
        if ln.startswith("[t="):
            simt = ln.split("]", 1)[0].replace("[t=", ""); break
    return {"Group": group, "Strategy": sid, "Registered_Name": name, "Seed": seed, "Valid": valid,
            "Black_Kills": k, "White_USV_Losses": l, "White_UAV_Losses": uav,
            "CER": (round(k / l, 3) if l else ("K:0" if k == 0 else "inf")),
            "Exchange_Result": ("EXCHANGE_WIN" if k > l else ("EXCHANGE_TIE" if k == l else "EXCHANGE_LOSS")),
            "Terminal_Result": m["result"], "Sim_Time": simt, "Wall_Time": wall,
            "ACE_SHA256": ACE_SHA, "Opponent_SHA256": ""}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="43001,43002")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    seeds = [int(s) for s in args.seeds.split(",")]
    os.makedirs(RAW, exist_ok=True)
    rows = []
    for group, sid, name, scen, profile in STRATS:
        for seed in seeds:
            r = run_one(group, sid, name, scen, profile, seed, args.port)
            rows.append(r)
            print(json.dumps(r, ensure_ascii=False), flush=True)
            with open(os.path.join(OUT, "ACE_12STRAT_N2_EPISODES.csv"), "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
    print("DONE", len(rows))


if __name__ == "__main__":
    main()
