#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""mechanism_metrics.py — compute outcome-independent mechanism metrics (proxy-based).

From agent stdout logs: Assignment Coverage, Never-assigned, TTFA, Commitment Utilization.
All use the step-level [ASSIGN] proxy (frozen W5 has no canonical owner-map instrumentation).
"""
import json, re, os
from collections import defaultdict


def parse_log(path):
    txt = open(path, encoding="utf-8", errors="replace").read()
    detects = []   # (t, target)
    assigns = []   # (t, white, target)
    kills = set()
    t = 0.0
    for line in txt.splitlines():
        m = re.search(r"\[t=([0-9,]+)s\]", line)
        if m:
            t = float(m.group(1).replace(",", ""))
        for mm in re.finditer(r"\[DETECT\]\s+(\S+)", line):
            detects.append((t, mm.group(1)))
        for mm in re.finditer(r"\[ASSIGN\]\s+(\S+)->(\S+)", line):
            assigns.append((t, mm.group(1), mm.group(2)))
        for mm in re.finditer(r"\[KILL\]\s+(\S+)", line):
            kills.add(mm.group(1))
    # commitment utilization from step lines
    util = []
    for m in re.finditer(r"USV: \d+/(\d+) \(avail=(\d+) int=(\d+) lock=(\d+)", txt):
        tot, av, it, lk = map(int, m.groups())
        if tot > 0:
            util.append((it + lk) / tot)
    return detects, assigns, kills, util


def load_results(logpath):
    res = []
    for line in open(logpath):
        line = line.strip()
        if "exchange_result" in line:
            try:
                res.append(json.loads(line[line.index("{"):]))
            except Exception:
                pass
    return res


def agent_stats(res, agent):
    # target-episode metrics
    detected = set()
    assigned = set()
    first_det = {}
    first_ass = {}
    ttfas = []
    utils = []
    for r in res:
        if r["agent"] != agent:
            continue
        sid, seed = r["strategy"], r["seed"]
        p = "auto_harness/combat_exchange/runs/s%d_%s_seed%s.log" % (sid, agent, seed)
        if not os.path.exists(p):
            continue
        detects, assigns, kills, util = parse_log(p)
        utils += util
        for t, tg in detects:
            detected.add((sid, tg))
            first_det.setdefault((sid, tg), t)
        for t, w, tg in assigns:
            assigned.add((sid, tg))
            if (sid, tg) not in first_ass or t < first_ass[(sid, tg)]:
                first_ass[(sid, tg)] = t
    for key in assigned:
        if key in first_det:
            ttfas.append(first_ass[key] - first_det[key])
    never = len(detected - assigned)
    cov = len(assigned & detected) / len(detected) if detected else 0.0
    mean_util = sum(utils) / len(utils) if utils else 0.0
    median_ttfa = sorted(ttfas)[len(ttfas) // 2] if ttfas else float("nan")
    return {
        "detected": len(detected),
        "assigned": len(assigned & detected),
        "never_assigned": never,
        "assignment_coverage": cov,
        "mean_commitment_utilization": mean_util,
        "median_ttfa": median_ttfa,
        "ttfa_assigned_count": len(ttfas),
    }


def main():
    res = load_results("/tmp/opencode/ace_dev.log")
    w5 = agent_stats(res, "W5")
    ace = agent_stats(res, "ACE")
    print("=== MECHANISM METRICS (proxy-based, completed episodes) ===")
    for k in ("detected", "assigned", "never_assigned", "assignment_coverage",
              "mean_commitment_utilization", "median_ttfa"):
        print(f"{k:32s} W5={w5[k]:.4f}  ACE={ace[k]:.4f}" if isinstance(w5[k], float) else f"{k:32s} W5={w5[k]}  ACE={ace[k]}")


if __name__ == "__main__":
    main()
