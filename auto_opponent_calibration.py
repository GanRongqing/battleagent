#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""auto_opponent_calibration.py — runner for AUTO_FEINT_SWITCH candidate.

Reuses the frozen run_opponent_formal metrics pipeline; behavior-neutral sidecars:
  - /status black behavior trace (via common_policy_calibration._sampler)
  - AUTO_EVENT_LOG (/tmp/opencode/auto_events.json) phase-event counters

Outputs under --out-dir:
  EPISODES.csv, AUTO_EVENTS.csv, traces/s<seed>_{black_behavior_trace.jsonl,
  autoevents.json, meta.json}
Resumable by (profile, seed) in EPISODES.csv.
"""
import argparse
import csv
import datetime
import hashlib
import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_opponent_formal as rof
from common_policy_calibration import _sampler, sha256, HASH_FILES

AUTO_PROFILE = "AUTO_FEINT_SWITCH"
AUTO_EVENT_FILE = "/tmp/opencode/auto_events.json"
INSTRUMENTATION_VERSION = "cal-v1 + auto-phase-events-v1"
FINGERPRINT_VERSION = "fp-v2"

EXTRA_COLS = ["seed", "auto_phase_switch_count", "auto_replan_count",
              "auto_response_trigger_fired", "auto_timeout_switch_fired",
              "auto_main_push_fired", "auto_reserve_commit_fired",
              "auto_degraded_count", "auto_feint_n", "auto_main_n", "auto_reserve_n",
              "auto_main_commit_time", "auto_phase", "auto_error"]


def load_done(csv_path):
    if not os.path.exists(csv_path):
        return set()
    try:
        rows = list(csv.DictReader(open(csv_path)))
    except Exception:
        return set()
    return {(r.get("opponent_profile"), int(r["seed"]))
            for r in rows if r.get("seed") and r.get("opponent_profile")}


def run(profile, scenario, seeds, out_dir, experiment_id):
    os.makedirs(out_dir, exist_ok=True)
    traces = os.path.join(out_dir, "traces")
    os.makedirs(traces, exist_ok=True)
    ep_path = os.path.join(out_dir, "EPISODES.csv")
    ev_path = os.path.join(out_dir, "AUTO_EVENTS.csv")
    hashes = {p: sha256(p) for p in HASH_FILES}
    hashes["opponent_auto_profiles.py"] = sha256("opponent_auto_profiles.py")
    done = load_done(ep_path)
    new = not os.path.exists(ep_path)
    fep = open(ep_path, "a", newline="", encoding="utf-8")
    wep = csv.DictWriter(fep, fieldnames=rof.COLS)
    if new:
        wep.writeheader(); fep.flush()
    fev = open(ev_path, "a", newline="", encoding="utf-8")
    wev = csv.DictWriter(fev, fieldnames=EXTRA_COLS)
    if not os.path.exists(ev_path) or os.path.getsize(ev_path) == 0:
        wev.writeheader(); fep.flush(); fflush(fev)
    rof.LOG_DIR = os.path.join(out_dir, "logs")
    os.makedirs(rof.LOG_DIR, exist_ok=True)

    for sd in seeds:
        if (profile, sd) in done:
            print(f"[SKIP] {profile} s{sd}", flush=True); continue
        print(f"[START] {profile} s{sd} {time.strftime('%H:%M:%S')}", flush=True)
        if os.path.exists(AUTO_EVENT_FILE):
            os.remove(AUTO_EVENT_FILE)
        trace_path = os.path.join(traces, f"s{sd}_black_behavior_trace.jsonl")
        if os.path.exists(trace_path):
            os.remove(trace_path)
        samp_t, samp_stop = _sampler(trace_path)
        samp_t.start()
        try:
            row = rof.run_one(experiment_id, scenario, profile, sd)
        except Exception as e:
            row = {c: None for c in rof.COLS}
            row["opponent_profile"] = profile; row["seed"] = sd
            row["http_or_trace_errors"] = 1; row["agent_rc"] = -1
            print(f"[ABNORMAL] {profile} s{sd}: {e}", flush=True)
        finally:
            samp_stop.set(); samp_t.join(timeout=6)
        ev = {}
        if os.path.exists(AUTO_EVENT_FILE):
            shutil.copy(AUTO_EVENT_FILE, os.path.join(traces, f"s{sd}_autoevents.json"))
            try:
                ev = json.load(open(AUTO_EVENT_FILE))
            except Exception:
                ev = {}
        wall = float(row.get("wall_time") or 0)
        infra = (wall < 20 and row.get("result") == "UNFINISHED") or row.get("http_or_trace_errors")
        if infra:
            print(f"  -> ABNORMAL (excluded, will rerun) result={row.get('result')} wall={wall}s", flush=True)
            continue
        meta = {"calibration_id": experiment_id, "requested_policy_id": profile,
                "effective_policy_id": profile, "scenario": scenario, "seed": sd,
                "bundle_hash": "black-auto-0001-v1:595e0f8bf8bea1b7",
                "w5_hash": hashes.get("agent_hybrid_v5.py"),
                "opponent_auto_module_hash": hashes.get("opponent_auto_profiles.py"),
                "instrumentation_version": INSTRUMENTATION_VERSION,
                "fingerprint_version": FINGERPRINT_VERSION,
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z"}
        json.dump(meta, open(os.path.join(traces, f"s{sd}_meta.json"), "w"), indent=2, ensure_ascii=False)
        wep.writerow({k: row.get(k) for k in rof.COLS}); fep.flush()
        roles = ev.get("roles", {})
        wev.writerow({"seed": sd,
                      "auto_phase_switch_count": ev.get("phase_switch_count"),
                      "auto_replan_count": ev.get("replan_count"),
                      "auto_response_trigger_fired": ev.get("response_trigger_fired"),
                      "auto_timeout_switch_fired": ev.get("timeout_switch_fired"),
                      "auto_main_push_fired": ev.get("main_push_fired"),
                      "auto_reserve_commit_fired": ev.get("reserve_commit_fired"),
                      "auto_degraded_count": ev.get("degraded_count"),
                      "auto_feint_n": roles.get("feint"), "auto_main_n": roles.get("main"),
                      "auto_reserve_n": roles.get("reserve"),
                      "auto_main_commit_time": ev.get("main_commit_time"),
                      "auto_phase": ev.get("phase"), "auto_error": ev.get("error")})
        fflush(fev)
        print(f"  -> {row.get('result')} clean={row.get('clean_win')} wall={wall}s "
              f"phase_switches={ev.get('phase_switch_count')} replan={ev.get('replan_count')} "
              f"response={ev.get('response_trigger_fired')} timeout={ev.get('timeout_switch_fired')}", flush=True)
    fep.close(); fev.close()
    print(f"[done] episodes in {ep_path}: {len(load_done(ep_path))}", flush=True)


def fflush(f):
    try:
        f.flush()
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default=AUTO_PROFILE)
    ap.add_argument("--scenario", default="S2")
    ap.add_argument("--seeds", nargs="*", type=int, required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--experiment-id", default="AUTO_0001")
    a = ap.parse_args()
    run(a.profile, a.scenario, a.seeds, a.out_dir, a.experiment_id)


if __name__ == "__main__":
    main()
