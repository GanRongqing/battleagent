#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""result_aggregator.py — single-writer aggregation of per-job result files into evaluation CSVs.

Workers never write the shared CSV; the scheduler calls aggregate() once at the end. CSV schema is
backward-compatible with the E2 runner (same columns), so existing readers keep working.
"""
import csv
import json
import os

EP_FIELDS = ["Strategy", "Policy", "Seed", "Actual_Engine_Seed", "Valid", "Black_Killed", "White_USV_Lost",
             "White_UAV_Lost", "Exchange_Ratio", "Exchange_Result", "Terminal_Result", "Sim_Time", "Wall_Time"]


def load_results(results_dir):
    rows = []
    if not os.path.isdir(results_dir):
        return rows
    for f in sorted(os.listdir(results_dir)):
        if f.endswith(".json"):
            try:
                d = json.load(open(os.path.join(results_dir, f), encoding="utf-8"))
                rows.append(d.get("Result", d))
            except Exception:
                pass
    return rows


def write_episodes(rows, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=EP_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in EP_FIELDS})


def main_results(rows):
    """8 rows: Strategy x Policy pooled kills/losses/ratio/wins."""
    from collections import defaultdict
    g = defaultdict(lambda: {"k": 0, "l": 0, "w": 0, "n": 0})
    for r in rows:
        if str(r.get("Valid")) not in ("True", "true", True):
            continue
        key = (r["Strategy"], r["Policy"])
        k = int(r.get("Black_Killed", 0)); l = int(r.get("White_USV_Lost", 0))
        g[key]["k"] += k; g[key]["l"] += l; g[key]["n"] += 1
        if k > l:
            g[key]["w"] += 1
    out = []
    for sid in ("W2-1", "W2-6", "W2-2", "W2-4"):
        for pol in ("ACE", "C7"):
            v = g.get((sid, pol))
            if not v:
                out.append({"Strategy": sid, "Policy": pol, "N": 0, "Black_Killed": "", "White_USV_Lost": "",
                            "Exchange_Ratio": "NOT_MEASURED", "Exchange_Wins": ""}); continue
            ratio = ("K:0" if (v["k"] == 0 and v["l"] == 0) else (round(v["k"] / v["l"], 3) if v["l"] else "inf"))
            out.append({"Strategy": sid, "Policy": pol, "N": v["n"], "Black_Killed": v["k"],
                        "White_USV_Lost": v["l"], "Exchange_Ratio": ratio,
                        "Exchange_Wins": f"{v['w']}/{v['n']}"})
    return out


def write_csv(rows, path, fields):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
