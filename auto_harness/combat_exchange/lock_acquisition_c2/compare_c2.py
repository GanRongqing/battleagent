#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""compare_c2.py — ACE vs C2 Assigned->First-Lock comparison on a single strategy/seed.

Recovers per-(USV,target) assignments from agent logs and lock events from game-log actions.
Usage: python compare_c2.py <strategy> <seed>
"""
import json
import math
import os
import re
import sys

ROOT = "/root/autodl-tmp/hsystem"
GAME = os.path.join(ROOT, "hsystem", "pomdp_api", "api_logs", "games")
RUNS = os.path.join(ROOT, "auto_harness", "combat_exchange", "runs")
LOCK_RANGE = 40000.0


def newest_game_log(after):
    best = None
    for fn in os.listdir(GAME):
        p = os.path.join(GAME, fn)
        if not fn.endswith(".json"):
            continue
        mt = os.path.getmtime(p)
        if mt >= after and (best is None or mt > best[1]):
            best = (p, mt)
    return best[0] if best else None


def analyze(agent_tag, strategy, seed):
    alog = os.path.join(RUNS, f"s{strategy}_{agent_tag}_seed{seed}.log")
    if not os.path.exists(alog):
        return None
    text = open(alog, encoding="utf-8", errors="replace").read()
    # assignments
    assigns = []
    t = 0.0
    for line in text.splitlines():
        m = re.search(r"\[t=([0-9,]+)s\]", line)
        if m:
            t = float(m.group(1).replace(",", ""))
        for mm in re.finditer(r"\[ASSIGN\]\s+(white_usv\d+)->([^(\s]+)", line):
            assigns.append((t, mm.group(1), mm.group(2)))
    mm = re.search(r"\[META\].*?friendly_usv_losses=(\d+)", text)
    loss = int(mm.group(1)) if mm else 0
    kills = len(set(re.findall(r"\[KILL\]\s+(\S+)", text)))
    # find game log whose mtime is closest after the agent log start
    t0 = os.path.getmtime(alog) - 4000
    gp = newest_game_log(t0 - 200)
    locks = set()
    if gp:
        d = json.load(open(gp))
        for s in d["steps"]:
            for a in s.get("actions", []):
                lm = re.search(r"(white_usv\d+) 锁定 (usv\d+)", a.get("动作", ""))
                if lm:
                    locks.add((lm.group(1), lm.group(2)))
    return dict(assigns=assigns, locks=locks, loss=loss, kills=kills, gl=gp)


def report(tag, r):
    if not r:
        print(f"{tag}: MISSING"); return
    a = r["assigns"]; nl = [x for x in a if (x[1], x[2]) not in r["locks"]]
    lr = (len(a) - len(nl)) / len(a) if a else 0
    print(f"{tag}: assignments={len(a)} locked={len(a)-len(nl)} lock_rate={lr*100:.1f}% "
          f"kills={r['kills']} losses={r['loss']} game_log={os.path.basename(r['gl']) if r['gl'] else None}")


if __name__ == "__main__":
    s = int(sys.argv[1]); sd = sys.argv[2]
    report("ACE", analyze("ACE", s, sd))
    report("C2 ", analyze("C2", s, sd))
