#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""run_replay_set.py — collect fully two-sided replayable episodes.

Records BOTH sides per poll into replay/replay_s<seed>.jsonl:
  white_usv / white_uav : own-state (position, velocity, speed, locking)
  black_visible         : radar-visible Black units (position, velocity)
  engaged               : locked Black unit names
plus the White agent log (events/assignments), episode META, EPISODES.csv and a
bundle README/MANIFEST. Behavior-neutral (read-only /status polling).

Usage:
  run_replay_set.py --profile B0_RANDOM --scenario S2 --seeds 7001..7010 --out-dir <dir>
"""
import argparse
import csv
import datetime
import hashlib
import json
import os
import shutil
import sys
import threading
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import run_opponent_formal as rof  # noqa: E402


def _unit(u):
    p = u.get("position") or [None, None]
    v = u.get("velocity") or [None, None]
    return {"name": u.get("name"), "x": p[0], "y": p[1],
            "vx": v[0], "vy": v[1], "speed": u.get("speed"),
            "alive": u.get("is_alive", True),
            "is_locking": u.get("is_locking"), "locking_unit": u.get("locking_unit")}


def full_sampler(path, poll=3.0):
    """Poll /status and write a two-sided per-poll snapshot."""
    import requests
    stop = threading.Event()

    def loop():
        while not stop.is_set():
            try:
                r = requests.get(rof.API + "/status", timeout=5)
                if r.status_code == 200:
                    st = r.json()
                    rs = st.get("资源快照", {}) or {}
                    us = rs.get("单位状态", {}) or {}
                    intel = (rs.get("观察信息", {}) or {}).get("white_observation", {}) or {}
                    hh, mm, ss = [int(x) for x in str(st.get("局内时间", "00:00:00")).split(":")]
                    rec = {
                        "sim_time": hh * 3600 + mm * 60 + ss,
                        "white_usv": [_unit(u) for u in us.get("white_usv_states", []) or []],
                        "white_uav": [_unit(u) for u in us.get("white_uav_states", []) or []],
                        "black_visible": [_unit(u) for u in intel.get("雷达捕获", []) or []],
                        "engaged": sorted({u.get("locking_unit") for u in
                                           (us.get("white_usv_states", []) or [])
                                           if u.get("is_locking") and u.get("locking_unit")}),
                    }
                    with open(path, "a", encoding="utf-8") as f:
                        f.write(json.dumps(rec) + "\n")
                    if st.get("已结束"):
                        break
            except Exception:
                pass
            stop.wait(poll)

    t = threading.Thread(target=loop, daemon=True)
    return t, stop


def sha(p):
    try:
        return hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]
    except Exception:
        return None


def run(profile, scenario, seeds, out_dir, experiment_id, agent=rof.AGENT):
    os.makedirs(out_dir, exist_ok=True)
    rof.AGENT = agent
    rof.LOG_DIR = os.path.join(out_dir, "logs")
    os.makedirs(rof.LOG_DIR, exist_ok=True)
    rdir = os.path.join(out_dir, "replay")
    os.makedirs(rdir, exist_ok=True)
    ep = os.path.join(out_dir, "EPISODES.csv")
    done = set()
    if os.path.exists(ep):
        done = {int(r["seed"]) for r in csv.DictReader(open(ep)) if r.get("seed")}
    new = not os.path.exists(ep)
    f = open(ep, "a", newline="", encoding="utf-8")
    w = csv.DictWriter(f, fieldnames=rof.COLS)
    if new:
        w.writeheader(); f.flush()
    for sd in seeds:
        if sd in done:
            print(f"[SKIP] s{sd}", flush=True); continue
        print(f"[START] s{sd} {time.strftime('%H:%M:%S')}", flush=True)
        rp = os.path.join(rdir, f"replay_s{sd}.jsonl")
        if os.path.exists(rp):
            os.remove(rp)
        t, stop = full_sampler(rp)
        t.start()
        try:
            row = rof.run_one(experiment_id, scenario, profile, sd)
        except Exception as e:
            row = {c: None for c in rof.COLS}; row["opponent_profile"] = profile; row["seed"] = sd
            row["http_or_trace_errors"] = 1; row["agent_rc"] = -1
            print("[ABNORMAL]", e, flush=True)
        finally:
            stop.set(); t.join(timeout=6)
        wall = float(row.get("wall_time") or 0)
        if (wall < 20 and row.get("result") == "UNFINISHED") or row.get("http_or_trace_errors"):
            print(f"  -> ABNORMAL excluded wall={wall}s", flush=True); continue
        meta = {"experiment_id": experiment_id, "profile": profile, "scenario": scenario,
                "seed": sd, "requested_policy_id": profile, "effective_policy_id": profile,
                "w5_hash": sha(os.path.join(ROOT, "agent_hybrid_v5.py")),
                "scenario_builder_hash": sha(os.path.join(ROOT, "hsystem", "sim_script",
                                                          "20250819TZB", "scenario_builder.py")),
                "agent": os.path.basename(agent),
                "instrumentation": "two-sided replay v1 (white_usv/white_uav/black_visible)",
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z"}
        json.dump(meta, open(os.path.join(rdir, f"meta_s{sd}.json"), "w"), indent=2, ensure_ascii=False)
        w.writerow({k: row.get(k) for k in rof.COLS}); f.flush()
        print(f"  -> {row.get('result')} clean={row.get('clean_win')} wall={wall}s", flush=True)
    f.close()
    # bundle manifest
    files = sorted(os.path.basename(p) for p in
                   [os.path.join(rdir, x) for x in os.listdir(rdir)])
    json.dump({"out_dir": out_dir, "profile": profile, "scenario": scenario,
               "seeds": list(seeds), "replay_files": files},
              open(os.path.join(out_dir, "REPLAY_MANIFEST.json"), "w"), indent=2)
    print(f"[done] {len(list(csv.DictReader(open(ep))))}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="B0_RANDOM")
    ap.add_argument("--scenario", default="S2")
    ap.add_argument("--seeds", nargs="*", type=int, required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--experiment-id", default="REPLAY_SET")
    ap.add_argument("--agent", default=os.path.join(ROOT, "agent_hybrid_v5.py"))
    a = ap.parse_args()
    run(a.profile, a.scenario, a.seeds, a.out_dir, a.experiment_id, a.agent)


if __name__ == "__main__":
    main()
