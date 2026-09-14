#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""common_policy_calibration.py — B0-B3 COMMON CALIBRATION (fp-v2 evidence).

Runs White=frozen W5 vs each of B0_RANDOM / B1_MULTI_AXIS /
B2_COORDINATED_PRESSURE / B3_ADAPTIVE on S2 with the SAME seeds 7001-7010.

Instrumentation is behavior-neutral: identical to run_opponent_formal.py
metrics pipeline; B3 runtime already emits legal adaptive event counters to
/tmp/opencode/b3_events.json which is snapshotted per episode (never reused).

Episode log / b3 snapshot / meta sidecar live under
policy_system/calibration/traces/<PROF>/s<seed>.*  (Auto Harness corpus and
5001-5010 untouched). Resumable by (profile, seed) in episodes CSV.
"""
import csv
import datetime
import hashlib
import json
import os
import sys
import threading
import time

import run_opponent_formal as rof

ROOT = os.path.dirname(os.path.abspath(__file__))
CAL = os.path.join(ROOT, "policy_system", "calibration")
TRACES = os.path.join(CAL, "traces")
CSV_EPISODES = os.path.join(CAL, "COMMON_CALIBRATION_EPISODES.csv")
B3_EVENT_FILE = "/tmp/opencode/b3_events.json"

SCENARIO = "S2"
SEEDS = list(range(7001, 7011))
PROFILES = ["B0_RANDOM", "B1_MULTI_AXIS", "B2_COORDINATED_PRESSURE", "B3_ADAPTIVE"]
INSTRUMENTATION_VERSION = "cal-v1 (metric collectors identical to run_opponent_formal)"
FINGERPRINT_VERSION = "fp-v2"
GIT_COMMIT = "calibration-dev-seeds-7001-7010"

HASH_FILES = [
    "agent_hybrid_v5.py",
    "opponent_profiles.py",
    "hsystem/sim_script/20250819TZB/scenario_composition.py",
    "hsystem/sim_script/20250819TZB/scenario_builder.py",
]


def sha256(path):
    try:
        with open(os.path.join(ROOT, path), "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:16]
    except Exception as e:
        return f"ERR:{e}"


def file_hashes():
    return {p: sha256(p) for p in HASH_FILES}


def load_done():
    if not os.path.exists(CSV_EPISODES):
        return set()
    try:
        rows = list(csv.DictReader(open(CSV_EPISODES)))
    except Exception:
        return set()
    return {(r["opponent_profile"], int(r["seed"]))
            for r in rows if r.get("opponent_profile") and r.get("seed")}


def normalize_csv():
    """Ensure the episodes CSV starts with a header line even if an earlier
    process was killed before flushing; keeps existing data rows."""
    if not os.path.exists(CSV_EPISODES):
        return
    with open(CSV_EPISODES, newline="", encoding="utf-8") as f:
        first = f.readline()
    if not first.strip():
        return
    if first.rstrip("\r\n").split(",")[0] == rof.COLS[0]:
        return
    rows = []
    with open(CSV_EPISODES, newline="", encoding="utf-8") as f:
        rd = csv.reader(f)
        for r in rd:
            if r and any(c.strip() for c in r):
                rows.append(r)
    with open(CSV_EPISODES, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(rof.COLS)
        for r in rows:
            if len(r) != len(rof.COLS):
                r = (r + [None] * len(rof.COLS))[:len(rof.COLS)]
            w.writerow(r)


def meta_sidecar(profile, seed, row, hashes):
    prof_dir = os.path.join(TRACES, profile)
    os.makedirs(prof_dir, exist_ok=True)
    meta = {
        "calibration_id": "COMMON_CAL_DEV",
        "requested_policy_id": profile,
        "effective_policy_id": profile if row.get("http_or_trace_errors", 0) == 0 and row.get("agent_rc") == 0 else f"{profile}_UNVERIFIED",
        "artifact_bundle_label": {"B0_RANDOM": "black-b0-v1",
                                  "B1_MULTI_AXIS": "black-b1-v1",
                                  "B2_COORDINATED_PRESSURE": "black-b2-v1",
                                  "B3_ADAPTIVE": "black-b3-v1"}[profile],
        "white_policy": "W5_frozen_agent_hybrid_v5",
        "w5_hash": hashes.get("agent_hybrid_v5.py"),
        "opponent_profiles_hash": hashes.get("opponent_profiles.py"),
        "scenario_composition_hash": hashes.get("hsystem/sim_script/20250819TZB/scenario_composition.py"),
        "scenario_builder_hash": hashes.get("hsystem/sim_script/20250819TZB/scenario_builder.py"),
        "scenario": SCENARIO,
        "seed": int(seed),
        "simulator_hash": "simserver-bundle (hash of engine inputs above)",
        "instrumentation_version": INSTRUMENTATION_VERSION,
        "fingerprint_version": FINGERPRINT_VERSION,
        "trace_schema_version": "ts-v1",
        "git_commit": GIT_COMMIT,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "abnormal": None,
    }
    p = os.path.join(prof_dir, f"s{seed}_meta.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    return p


def _sampler(trace_path, poll=3.0):
    """Behavior-neutral sidecar: polls /status (White legal view) and records
    radar-visible Black positions/engagements to black_behavior_trace.jsonl.
    Read-only, same source as OpponentMetrics. Marked proxy geometry."""
    import requests

    def _observe(st, f):
        hh, mm, ss = [int(x) for x in str(st.get("局内时间", "00:00:00")).split(":")]
        now = hh * 3600 + mm * 60 + ss
        rs = st.get("资源快照", {}) or {}
        intel = (rs.get("观察信息", {}) or {}).get("white_observation", {}) or {}
        active = intel.get("雷达捕获", []) or []
        engaged = set()
        for u in rs.get("单位状态", {}).get("white_usv_states", []) or []:
            if u.get("is_locking") and u.get("locking_unit"):
                engaged.add(u["locking_unit"])
        pts = [{"name": e.get("name"),
                "x": (e.get("position") or [0, 0])[0],
                "y": (e.get("position") or [0, 0])[1]}
               for e in active if e.get("position")]
        f.write(json.dumps({"sim_time": now, "visible_count": len(active),
                            "positions": pts, "engaged": sorted(engaged)}))
        f.write("\n")
        f.flush()

    stop = threading.Event()

    def _loop():
        try:
            while not stop.is_set():
                try:
                    r = requests.get(rof.API + "/status", timeout=5)
                    if r.status_code == 200:
                        st = r.json()
                        with open(trace_path, "a", encoding="utf-8") as f:
                            _observe(st, f)
                            if st.get("已结束"):
                                break
                except Exception:
                    pass
                stop.wait(poll)
        except Exception:
            pass

    t = threading.Thread(target=_loop, daemon=True)
    return t, stop


def run_all(profiles=None, seeds=None):
    profiles = profiles or PROFILES
    seeds = seeds or SEEDS
    os.makedirs(TRACES, exist_ok=True)
    hashes = file_hashes()
    normalize_csv()
    done = load_done()
    new = not os.path.exists(CSV_EPISODES)
    with open(CSV_EPISODES, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=rof.COLS)
        if new:
            w.writeheader()
            f.flush()
        for prof in profiles:
            prof_dir = os.path.join(TRACES, prof)
            os.makedirs(prof_dir, exist_ok=True)
            rof.LOG_DIR = os.path.join(prof_dir, "logs")
            os.makedirs(rof.LOG_DIR, exist_ok=True)
            for sd in seeds:
                key = (prof, sd)
                if key in done:
                    print(f"[SKIP] {prof} s{sd}", flush=True)
                    continue
                print(f"[START] {prof} s{sd} {time.strftime('%H:%M:%S')}", flush=True)
                try:
                    if prof == "B3_ADAPTIVE" and os.path.exists(B3_EVENT_FILE):
                        os.remove(B3_EVENT_FILE)
                    trace_path = os.path.join(prof_dir, f"s{sd}_black_behavior_trace.jsonl")
                    if os.path.exists(trace_path):
                        os.remove(trace_path)
                    samp_t, samp_stop = _sampler(trace_path)
                    samp_t.start()
                    row = rof.run_one("COMMON_CAL_DEV", SCENARIO, prof, sd)
                    samp_stop.set(); samp_t.join(timeout=6)
                except Exception as e:
                    try:
                        samp_stop.set()
                    except Exception:
                        pass
                    row = {c: None for c in rof.COLS}
                    row["opponent_profile"] = prof
                    row["seed"] = sd
                    row["http_or_trace_errors"] = 1
                    row["agent_rc"] = -1
                    print(f"[ABNORMAL] {prof} s{sd}: {e}", flush=True)
                try:
                    wall = float(row.get("wall_time") or 0)
                except Exception:
                    wall = 0
                infra_fail = (wall < 20 and row.get("result") == "UNFINISHED") or \
                    row.get("http_or_trace_errors") or row.get("agent_rc") not in (0, None)
                if infra_fail:
                    # do NOT record as a valid completed episode; allow rerun of same seed
                    try:
                        mp = os.path.join(prof_dir, f"s{sd}_meta.json")
                        import json as _json
                        meta = _json.load(open(mp))
                        meta["abnormal"] = "INFRA_FAILURE (wall<20s / UNFINISHED) - excluded, will rerun"
                        meta["effective_policy_id"] = f"{prof}_UNVERIFIED"
                        _json.dump(meta, open(mp, "w"), indent=2, ensure_ascii=False)
                    except Exception:
                        pass
                    print(f"  -> ABNORMAL (excluded, will rerun) result={row.get('result')} "
                          f"wall={wall}s rc={row.get('agent_rc')}", flush=True)
                    continue
                meta_sidecar(prof, sd, row, hashes)
                if prof == "B3_ADAPTIVE" and os.path.exists(B3_EVENT_FILE):
                    dst = os.path.join(prof_dir, f"s{sd}_b3events.json")
                    try:
                        import shutil
                        shutil.copy(B3_EVENT_FILE, dst)
                    except Exception:
                        pass
                w.writerow({k: row.get(k) for k in rof.COLS})
                f.flush()
                print(f"  -> {row.get('result')} clean={row.get('clean_win')} usv_dead={row.get('friendly_usv_dead')} "
                      f"kills={row.get('enemy_combat_killed_event')} wall={row.get('wall_time')}s", flush=True)
    print(f"[done] episodes in {CSV_EPISODES}: {len(load_done())}", flush=True)


if __name__ == "__main__":
    sys.exit(run_all())
