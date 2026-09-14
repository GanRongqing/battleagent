#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""run_white_phase1.py — paired W5 vs candidate runner for Phase 1.

Reuses the frozen run_opponent_formal metrics pipeline; only the agent script is
configurable (W5 or the anti-leak candidate). Snapshots the candidate mechanism
event log. Resumable by (agent_tag, seed).
"""
import argparse
import csv
import json
import os
import shutil
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import run_opponent_formal as rof  # noqa: E402

W8_EVENT = "/tmp/opencode/w8_containment_events.json"


def load_done(path):
    if not os.path.exists(path):
        return set()
    try:
        return {int(r["seed"]) for r in csv.DictReader(open(path)) if r.get("seed")}
    except Exception:
        return set()


def run(agent, tag, scenario, seeds, out_dir, exp_id, profile="B3_ADAPTIVE"):
    os.makedirs(out_dir, exist_ok=True)
    rof.AGENT = agent
    rof.LOG_DIR = os.path.join(out_dir, "logs")
    os.makedirs(rof.LOG_DIR, exist_ok=True)
    ep = os.path.join(out_dir, "EPISODES.csv")
    done = load_done(ep)
    new = not os.path.exists(ep)
    f = open(ep, "a", newline="", encoding="utf-8")
    w = csv.DictWriter(f, fieldnames=rof.COLS)
    if new:
        w.writeheader(); f.flush()
    for sd in seeds:
        if sd in done:
            print(f"[SKIP] {tag} s{sd}", flush=True); continue
        print(f"[START] {tag} s{sd} {time.strftime('%H:%M:%S')}", flush=True)
        if tag == "cand" and os.path.exists(W8_EVENT):
            os.remove(W8_EVENT)
        if tag == "cand":
            os.environ["W8_AUDIT_LOG"] = os.path.join(out_dir, f"s{sd}_audit.jsonl")
        try:
            row = rof.run_one(exp_id, scenario, profile, sd)
        except Exception as e:
            row = {c: None for c in rof.COLS}; row["opponent_profile"] = profile; row["seed"] = sd
            row["http_or_trace_errors"] = 1; row["agent_rc"] = -1
            print(f"[ABNORMAL] {tag} s{sd}: {e}", flush=True)
        wall = float(row.get("wall_time") or 0)
        if (wall < 20 and row.get("result") == "UNFINISHED") or row.get("http_or_trace_errors"):
            print(f"  -> ABNORMAL (excluded, will rerun) wall={wall}s", flush=True)
            continue
        if tag == "cand" and os.path.exists(W8_EVENT):
            shutil.copy(W8_EVENT, os.path.join(out_dir, f"s{sd}_w8events.json"))
        w.writerow({k: row.get(k) for k in rof.COLS}); f.flush()
        print(f"  -> {row.get('result')} clean={row.get('clean_win')} brk={row.get('enemy_breakthrough_count')} "
              f"loss={row.get('friendly_usv_dead')} wall={wall}s", flush=True)
    f.close()
    print(f"[done] {tag}: {len(load_done(ep))}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--scenario", default="S2")
    ap.add_argument("--seeds", nargs="*", type=int, required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--experiment-id", default="WHITE_PHASE1")
    a = ap.parse_args()
    run(a.agent, a.tag, a.scenario, a.seeds, a.out_dir, a.experiment_id)


if __name__ == "__main__":
    main()
