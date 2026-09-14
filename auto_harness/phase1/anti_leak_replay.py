#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""anti_leak_replay.py — OFFLINE mechanism replay on the frozen 6001-6100 corpus.

Proxy only: the corpus White logs give per-step TRACKS (vis/lost/engaged) and TOP
visible enemy positions, but NOT per-step White USV positions. So we can measure
"high crossing-risk with NO assigned/engaged blocker" (a lower bound on the real
unblocked condition) and whether the estimator would fire. This is a MECHANISM
sanity check, NOT an outcome claim (B28).
"""
import csv
import json
import math
import os
import re
import statistics as st

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DERIVED = os.path.join(ROOT, "auto_harness", "phase0", "analysis", "AUTO_HARNESS_DERIVED.csv")
OUT = os.path.join(ROOT, "auto_harness", "phase1")
BREAK_X = 50000.0
ETA_CRITICAL, ETA_HIGH, ETA_MEDIUM = 3000.0, 6000.0, 10000.0
STEP = re.compile(r"\[t=([0-9,]+)s\] step=\d+.*?TRACKS: vis=(\d+) lost=(\d+) engaged=(\d+)")
TOP = re.compile(r"black_usv\d+\(x([\d,]+)\)")


def parse(path):
    steps = []
    try:
        txt = open(path, encoding="utf-8", errors="replace").read()
    except Exception:
        return steps
    for line in txt.splitlines():
        m = STEP.search(line)
        if not m:
            continue
        t = int(m.group(1).replace(",", ""))
        vis, lost, eng = int(m.group(2)), int(m.group(3)), int(m.group(4))
        tops = TOP.findall(line)
        steps.append((t, vis, lost, eng, tops))
    return steps


def replay(path):
    steps = parse(path)
    last = {}
    first_high = None
    first_crit = None
    unblocked_high = 0
    unblocked_crit = 0
    for (t, vis, lost, eng, tops) in steps:
        for raw in tops:
            x = float(raw.replace(",", ""))
            # velocity proxy: only x known; use consecutive x of same slot is unreliable
        # estimator on available x + assumed closing (cannot get vx from TOP reliably)
        # Use boundary proximity as the risk proxy: x < BREAK_X + ETA_HIGH*closing_speed
        # closing speed assumed 10 m/s (Black commanded speed) -> x within 60km of line.
        near = [float(r.replace(",", "")) for r in tops]
        for x in near:
            eta = max(0.0, (x - BREAK_X) / 10.0)
            if eta <= ETA_HIGH:
                if eng == 0:
                    unblocked_high += 1
                    if first_high is None:
                        first_high = t
                if eta <= ETA_CRITICAL and eng == 0:
                    unblocked_crit += 1
                    if first_crit is None:
                        first_crit = t
    return {"steps": len(steps), "unblocked_high_steps": unblocked_high,
            "unblocked_crit_steps": unblocked_crit, "first_high": first_high,
            "first_crit": first_crit, "resolution": steps[-1][0] if steps else None}


def run():
    rows = list(csv.DictReader(open(DERIVED)))
    fail = [r for r in rows if r["clean_win"] != "1"]
    clean = [r for r in rows if r["clean_win"] == "1"]
    fr = [replay(r["trace_path"]) for r in fail]
    cr = [replay(r["trace_path"]) for r in clean]
    def cov(group, key):
        return round(sum(1 for x in group if x[key] > 0) / max(1, len(group)), 3)
    lead = [x["first_high"] for x in fr if x["first_high"] is not None]
    report = {
        "corpus": "6001-6100 (B3_ADAPTIVE, frozen, read-only)",
        "n_fail": len(fail), "n_clean": len(clean),
        "failure_trigger_coverage_high": cov(fr, "unblocked_high_steps"),
        "failure_trigger_coverage_crit": cov(fr, "unblocked_crit_steps"),
        "clean_false_trigger_rate_high": cov(cr, "unblocked_high_steps"),
        "clean_false_trigger_rate_crit": cov(cr, "unblocked_crit_steps"),
        "median_trigger_lead_time_s": round(st.median(lead), 1) if lead else None,
        "p25_lead": round(st.quantiles(lead, n=4)[0], 1) if len(lead) >= 4 else None,
        "p75_lead": round(st.quantiles(lead, n=4)[2], 1) if len(lead) >= 4 else None,
        "mean_unblocked_high_steps_fail": round(st.mean(x["unblocked_high_steps"] for x in fr), 2),
        "mean_unblocked_high_steps_clean": round(st.mean(x["unblocked_high_steps"] for x in cr), 2),
        "note": "PROXY: no per-step White USV positions in corpus; risk uses boundary proximity "
                "and engaged==0 as the unblocked proxy. Mechanism sanity only, not outcome proof.",
    }
    json.dump(report, open(os.path.join(OUT, "ANTI_LEAK_REPLAY.json"), "w"), indent=2)
    lines = ["# Anti-Leak Offline Replay (proxy, corpus 6001-6100)", "",
             f"- failures={report['n_fail']} clean={report['n_clean']}",
             f"- failure trigger coverage (HIGH proxy): {report['failure_trigger_coverage_high']}",
             f"- failure trigger coverage (CRITICAL proxy): {report['failure_trigger_coverage_crit']}",
             f"- clean false-trigger rate (HIGH proxy): {report['clean_false_trigger_rate_high']}",
             f"- clean false-trigger rate (CRITICAL proxy): {report['clean_false_trigger_rate_crit']}",
             f"- median actionable lead (first HIGH-proxy step): {report['median_trigger_lead_time_s']} s",
             f"- mean unblocked-high steps: fail {report['mean_unblocked_high_steps_fail']} vs "
             f"clean {report['mean_unblocked_high_steps_clean']}", "",
             report["note"]]
    open(os.path.join(OUT, "ANTI_LEAK_REPLAY_ANALYSIS.md"), "w").write("\n".join(lines))
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    run()
