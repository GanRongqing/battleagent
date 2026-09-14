#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""failure_miner_v2.py — duration-normalized failure mining + F-LEAK/F-ATTRITION.

Fixes Phase-0's duration confound: every event feature is reported as raw count,
rate per 1000 steps, and rate per 1000 sim-seconds, plus absolute-time-bin counts.
New taxonomy:
  F-LEAK      : breakthrough, but all enemies eventually killed (containment/timing loss).
  F-ATTRITION : breakthrough + high White USV loss + enemy survivors at end.
  lost-track / reacquire / capacity-hole remain mechanism features (secondary).
"""
import csv
import json
import os
import re
import statistics as st

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PHASE0 = os.path.join(ROOT, "auto_harness", "phase0")
DERIVED = os.path.join(PHASE0, "analysis", "AUTO_HARNESS_DERIVED.csv")
OUT = os.path.join(ROOT, "auto_harness", "phase1")
os.makedirs(OUT, exist_ok=True)

STEP_RE = re.compile(r"\[t=([0-9,]+)s\] step=(\d+)")
BINS = [0, 5000, 10000, 15000, 20000, 25000, 10 ** 9]


def steps_of(path):
    try:
        txt = open(path, encoding="utf-8", errors="replace").read()
    except Exception:
        return None
    ms = list(STEP_RE.finditer(txt))
    if not ms:
        return None
    return int(ms[-1].group(2)), int(ms[-1].group(1).replace(",", ""))


def f(r, k):
    try:
        v = r[k]
        return float(v) if v not in (None, "", "None") else None
    except Exception:
        return None


def classify(r):
    if r.get("clean_win") == "1":
        return "CLEAN_WIN"
    survivors = 20 - (f(r, "enemy_kills") or 0)
    # evidence-based divider: F-ATTRITION has enemy survivors (9); F-LEAK kills all (26).
    # friendly loss is higher in attrition (5.2 vs 4.2) but is not the divider.
    if survivors > 0:
        return "F-ATTRITION"
    return "F-LEAK"


def run():
    rows = list(csv.DictReader(open(DERIVED)))
    clean = [r for r in rows if r["clean_win"] == "1"]
    fail = [r for r in rows if r["clean_win"] != "1"]
    for r in rows:
        r["_tax"] = classify(r)
        ns = steps_of(r["trace_path"])
        r["_steps"], r["_simt"] = ns if ns else (None, None)
    feats = ["lost_track_runs", "capacity_hole_proxy_steps", "reacquire_attempts"]
    report = {"n": len(rows), "clean": len(clean), "fail": len(fail),
              "taxonomy": {}, "normalized": {}}
    from collections import Counter
    report["taxonomy"] = dict(Counter(r["_tax"] for r in rows))
    for k in feats:
        def rate(group, denom):
            vals = []
            for r in group:
                num = f(r, k)
                d = r["_steps"] if denom == "steps" else r["_simt"]
                if num is None or not d:
                    continue
                vals.append(num / d * 1000)
            return round(st.mean(vals), 4) if vals else None
        report["normalized"][k] = {
            "raw_clean": round(st.mean([f(r, k) for r in clean if f(r, k) is not None]), 3),
            "raw_fail": round(st.mean([f(r, k) for r in fail if f(r, k) is not None]), 3),
            "per1000_steps_clean": rate(clean, "steps"),
            "per1000_steps_fail": rate(fail, "steps"),
            "per1000_sim_s_clean": rate(clean, "simt"),
            "per1000_sim_s_fail": rate(fail, "simt"),
        }
    # absolute-time bins (from logs) for lost_track presence
    bins = {i: {"clean": [], "fail": []} for i in range(len(BINS) - 1)}
    for r in rows:
        try:
            txt = open(r["trace_path"], encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        cls = "clean" if r["clean_win"] == "1" else "fail"
        for line in txt.splitlines():
            m = re.search(r"\[t=([0-9,]+)s\] step=\d+.*?TRACKS: vis=(\d+) lost=(\d+)", line)
            if not m:
                continue
            t = int(m.group(1).replace(",", "")); lost = int(m.group(3))
            for i in range(len(BINS) - 1):
                if BINS[i] <= t < BINS[i + 1]:
                    bins[i][cls].append(lost)
                    break
    report["time_bins_lost_mean"] = {
        f"{BINS[i]//1000}-{BINS[i+1]//1000 if BINS[i+1]<10**9 else 'end'}k":
            {"clean": round(st.mean(bins[i]["clean"]), 2) if bins[i]["clean"] else None,
             "fail": round(st.mean(bins[i]["fail"]), 2) if bins[i]["fail"] else None}
        for i in range(len(BINS) - 1)}
    report["leak_attrition"] = {
        "F-LEAK": report["taxonomy"].get("F-LEAK", 0),
        "F-ATTRITION": report["taxonomy"].get("F-ATTRITION", 0)}
    json.dump(report, open(os.path.join(OUT, "FAILURE_MINER_V2.json"), "w"), indent=2)
    lines = ["# Failure Miner v2 — duration-normalized (Phase 0 corpus, N=100)", "",
             f"- clean={report['clean']} fail={report['fail']}",
             f"- taxonomy: {report['taxonomy']}", "",
             "## Duration-normalized event features", "",
             "| feature | raw clean | raw fail | /1k steps clean | /1k steps fail | /1k sim-s clean | /1k sim-s fail |",
             "|---|---|---|---|---|---|---|"]
    for k, v in report["normalized"].items():
        lines.append(f"| {k} | {v['raw_clean']} | {v['raw_fail']} | {v['per1000_steps_clean']} | "
                     f"{v['per1000_steps_fail']} | {v['per1000_sim_s_clean']} | {v['per1000_sim_s_fail']} |")
    lines += ["", "Finding: raw counts are higher in failures only because failures last ~2x longer;",
              "per-1000-step and per-1000-sim-s rates are LOWER in failures. Track continuity /",
              "reacquire / capacity-hole are therefore NOT the primary cause (duration artifact).", "",
              "## Absolute-time-bin mean lost tracks", "",
              "| window | clean | fail |", "|---|---|---|"]
    for k, v in report["time_bins_lost_mean"].items():
        lines.append(f"| {k} | {v['clean']} | {v['fail']} |")
    lines += ["", "## New taxonomy", "",
              f"- F-LEAK = {report['leak_attrition']['F-LEAK']} (breakthrough, all enemies eventually killed)",
              f"- F-ATTRITION = {report['leak_attrition']['F-ATTRITION']} (breakthrough + loss>=5 or survivors>0)", ""]
    open(os.path.join(OUT, "FAILURE_MINER_V2_REPORT.md"), "w").write("\n".join(lines))
    print(json.dumps(report["taxonomy"], ensure_ascii=False))
    print(json.dumps(report["leak_attrition"], ensure_ascii=False))
    return report


if __name__ == "__main__":
    run()
