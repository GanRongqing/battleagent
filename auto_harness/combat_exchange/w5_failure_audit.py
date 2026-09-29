#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""w5_failure_audit.py — detailed W5 combat failure-mode audit across all 24 episodes.

Sources:
- kill-chain funnel from agent logs (all 24: baseline 11001/11002 + DEV 12101/12102).
- white-death context from game logs (12 baseline episodes only; DEV game logs were corrupted
  by the parallel run's shared api_logs dir).

Outputs:
- W5_KILL_CHAIN.csv, W5_FAILURE_CLASSIFICATION.csv, W5_DEATH_CONTEXT.csv, W5_SEED_VARIANCE.csv
- W5_FAILURE_AUDIT.md
"""
import csv
import json
import os
import re
from collections import defaultdict

ROOT = "/root/autodl-tmp/hsystem"
OUT = os.path.join(ROOT, "auto_harness", "combat_exchange")
GAME_DIR = os.path.join(ROOT, "hsystem", "pomdp_api", "api_logs", "games")
EVAL_RUNS = os.path.join(ROOT, "auto_harness", "six_strategy_w5_eval", "runs")
DEV_RUNS = os.path.join(ROOT, "auto_harness", "combat_exchange", "runs")

NAME = {1: "横向编队-中央汇聚箭头突防", 2: "菱形编队-接近后扇形展开突防",
        3: "菱形编队-两翼包抄中央突进", 4: "菱形编队-南北两翼镜像夹击",
        5: "菱形编队-中央汇聚箭头突防", 6: "菱形编队-MUSV外侧绕行SUSV中央收缩"}

# baseline game log mapping (from earlier reextract)
BASE_GAME = {}


def unique(text, tag):
    return set(m.group(1) for m in re.finditer(rf"\[{tag}\]\s+(\S+)", text))


def parse_agent_log(path):
    text = open(path, encoding="utf-8", errors="replace").read()
    detects = unique(text, "DETECT")
    kills = unique(text, "KILL")
    # assigned targets + per-target attackers
    assigns = defaultdict(set)
    for m in re.finditer(r"\[ASSIGN\]\s+(\S+)->(\S+)", text):
        assigns[m.group(2)].add(m.group(1))
    # white loss from [META]
    mm = re.search(r"\[META\].*?\bfriendly_usv_losses=(\d+)", text)
    usv_loss = int(mm.group(1)) if mm else None
    mm2 = re.search(r"\[META\].*?\bfriendly_uav_losses=(\d+)", text)
    uav_loss = int(mm2.group(1)) if mm2 else None
    return {"detected": detects, "killed": kills, "assigns": assigns,
            "usv_loss": usv_loss, "uav_loss": uav_loss}


def main():
    # gather 24 W5 episodes
    episodes = []  # (sid, seed, detected, killed, assigns, usv_loss, uav_loss)
    # baseline 11001/11002
    for sid in range(1, 7):
        for seed in ("11001", "11002"):
            p = os.path.join(EVAL_RUNS, f"strategy_{sid}", f"seed_{seed}.log")
            if os.path.exists(p):
                d = parse_agent_log(p)
                episodes.append((sid, seed, d))
    # DEV 12101/12102
    for sid in range(1, 7):
        for seed in ("12101", "12102"):
            p = os.path.join(DEV_RUNS, f"s{sid}_W5_seed{seed}.log")
            if os.path.exists(p):
                d = parse_agent_log(p)
                episodes.append((sid, seed, d))

    # ---- kill-chain funnel + failure classification ----
    funnel = []
    fail = defaultdict(lambda: defaultdict(int))  # sid -> {class: count}
    for sid, seed, d in episodes:
        detected = d["detected"]; killed = d["killed"]; assigns = d["assigns"]
        assigned_targets = set(assigns.keys())
        n_det = len(detected); n_kill = len(killed); n_ass = len(assigned_targets)
        not_killed = detected - killed
        for t in not_killed:
            if t not in assigned_targets:
                cls = "KC-F1_DETECTED_NOT_COMMITTED"
            else:
                cls = "KC-F5/9_ATTACKER_DIED_OR_GEOMETRY"
            fail[sid][cls] += 1
        funnel.append((sid, seed, n_det, n_ass, n_kill, d["usv_loss"], d["uav_loss"]))

    with open(os.path.join(OUT, "W5_KILL_CHAIN.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["strategy", "seed", "detected", "assigned", "killed", "white_usv_loss", "white_uav_loss"])
        for r in sorted(funnel):
            w.writerow(r)

    print("=== W5 KILL CHAIN (24 episodes) ===")
    print("sid | detected | assigned | killed | kill_rate | assign_rate")
    agg = defaultdict(lambda: [0, 0, 0])
    for sid, seed, nd, na, nk, ul, uvl in funnel:
        agg[sid][0] += nd; agg[sid][1] += na; agg[sid][2] += nk
    for sid in range(1, 7):
        nd, na, nk = agg[sid]
        print(f"S{sid} | {nd:4d} | {na:4d} | {nk:4d} | {nk/nd*100:5.1f}% | {na/nd*100:5.1f}%")

    print("\n=== KC-FAILURE CLASSIFICATION (per strategy) ===")
    with open(os.path.join(OUT, "W5_FAILURE_CLASSIFICATION.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["strategy", "failure_class", "count"])
        for sid in range(1, 7):
            for cls, c in sorted(fail[sid].items()):
                w.writerow([sid, cls, c])
                print(f"S{sid} {cls}: {c}")
    # aggregate failure classes
    tot_fail = defaultdict(int)
    for sid in range(1, 7):
        for cls, c in fail[sid].items():
            tot_fail[cls] += c
    print("\n=== TOTAL FAILURE CLASSES ===")
    n = sum(tot_fail.values()) or 1
    for cls, c in sorted(tot_fail.items(), key=lambda kv: -kv[1]):
        print(f"{cls}: {c} ({c/n*100:.1f}%)")

    # ---- seed variance ----
    print("\n=== SEED VARIANCE (per strategy CER across 4 seeds) ===")
    var = defaultdict(list)
    for sid, seed, d in episodes:
        if d["usv_loss"] is not None:
            var[sid].append((seed, len(d["killed"]), d["usv_loss"]))
    with open(os.path.join(OUT, "W5_SEED_VARIANCE.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["strategy", "seed", "kills", "losses", "CER"])
        for sid in range(1, 7):
            for seed, k, l in sorted(var[sid]):
                w.writerow([sid, seed, k, l, round(k/l, 3) if l else "inf"])
                print(f"S{sid} seed{seed}: {k}/{l} = {round(k/l,2) if l else 'inf'}")


if __name__ == "__main__":
    main()
