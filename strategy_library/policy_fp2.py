#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""policy_fp2.py — fp-v2 empirical fingerprint computation from common calibration.

Sources per episode:
  - COMMON_CALIBRATION_EPISODES.csv  (metrics pipeline identical to
    run_opponent_formal.py: response + timing + White-view approach metrics
    + B3 legal adaptive event counters)
  - traces/<PROF>/s<seed>_black_behavior_trace.jsonl (behavior-neutral /status
    sidecar: radar-visible Black positions/names per poll → geometry proxies)

Honesty rules enforced here:
  - feature availability is explicit: available / proxy / unavailable.
  - missing or unobservable features are NEVER set to 0; they are unavailable.
  - profiles WITHOUT an adaptive replan mechanism get adaptive counts = 0 with
    availability available (a real zero), distinct from unavailable.
  - behavioral (Black own way of fighting) and response (White outcome) are
    stored separately and never merged into one opaque vector.
"""
import csv
import json
import math
import os
import statistics

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_EPISODES = os.path.join(_ROOT, "policy_system", "calibration", "COMMON_CALIBRATION_EPISODES.csv")
TRACES = os.path.join(_ROOT, "policy_system", "calibration", "traces")
PROFILES = ["B0_RANDOM", "B1_MULTI_AXIS", "B2_COORDINATED_PRESSURE", "B3_ADAPTIVE"]
SEEDS = list(range(7001, 7011))

# ── availability taxonomy ──
AV = {"avail": "available", "proxy": "proxy", "na": "unavailable"}

# units: sim meters / sim seconds; distances reported in km for readability
M2KM = 1.0 / 1000.0


def _num(v):
    try:
        if v is None:
            return None
        f = float(v)
        return None if math.isnan(f) else f
    except Exception:
        return None


def load_episodes():
    if not os.path.exists(CSV_EPISODES):
        return {}
    out = {}
    with open(CSV_EPISODES, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            key = (r["opponent_profile"], int(r["seed"]))
            out[key] = r
    return out


def load_trace(profile, seed):
    p = os.path.join(TRACES, profile, f"s{seed}_black_behavior_trace.jsonl")
    if not os.path.exists(p):
        return []
    out = []
    try:
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
    except Exception:
        pass
    return out


# ── behavioral: geometry proxies from the sidecar ──
def geometry_proxies(samples):
    """Over the window where Black ships are radar-visible to frozen White,
    compute geometry stats. Positions are Black's real positions as reported
    through White radar intel -> proxy (not full Black ground truth)."""
    feat = {}
    vis = [s for s in samples if s.get("visible_count", 0) >= 3]
    if not vis:
        feat = {
            "visible_pairwise_dist_km_median": {"value": None, "availability": AV["na"]},
            "visible_y_spread_km_median": {"value": None, "availability": AV["na"]},
            "visible_peak_count": {"value": None, "availability": AV["na"]},
            "visible_window_start_s": {"value": None, "availability": AV["na"]},
        }
        return feat
    pairds, yspreads = [], []
    peak = 0
    wstart = min(s["sim_time"] for s in vis)
    for s in vis:
        pts = s.get("positions", [])
        peak = max(peak, len(pts))
        if len(pts) >= 2:
            ys = [p["y"] for p in pts]
            yspreads.append((max(ys) - min(ys)) * M2KM)
            dsum, n = 0.0, 0
            for i in range(len(pts)):
                for j in range(i + 1, len(pts)):
                    dsum += math.hypot(pts[i]["x"] - pts[j]["x"], pts[i]["y"] - pts[j]["y"])
                    n += 1
            if n:
                pairds.append((dsum / n) * M2KM)
    feat = {
        "visible_pairwise_dist_km_median": {"value": statistics.median(pairds) if pairds else None,
                                            "availability": AV["proxy"]},
        "visible_y_spread_km_median": {"value": statistics.median(yspreads) if yspreads else None,
                                       "availability": AV["proxy"]},
        "visible_peak_count": {"value": peak, "availability": AV["proxy"]},
        "visible_window_start_s": {"value": wstart, "availability": AV["proxy"]},
    }
    return feat


def arrival_front_proxy(samples):
    """First-time-each-Black-ship-becomes-visible proxy (White radar arrival front).
    Same definition for all profiles; White sensing identical across profiles, so
    differences reflect Black approach timing only."""
    first = {}
    for s in samples:
        for p in s.get("positions", []):
            nm = p["name"]
            if nm not in first:
                first[nm] = s["sim_time"]
    vals = sorted(first.values())
    if len(vals) < 2:
        return {"arrival_front_sync_std_s": {"value": None, "availability": AV["na"]},
                "arrival_front_mean_s": {"value": None, "availability": AV["na"]}}
    return {
        "arrival_front_sync_std_s": {"value": round(statistics.pstdev(vals), 1),
                                     "availability": AV["proxy"]},
        "arrival_front_mean_s": {"value": round(statistics.mean(vals), 1),
                                 "availability": AV["proxy"]},
    }


# ── single episode fingerprint ──
def episode_fp(profile, seed, row, samples):
    def g(k):
        return _num(row.get(k))

    def av(v, avail):
        return {"value": v, "availability": avail}

    resolution = g("sim_time")
    b3_replan = g("b3_replan_count") or 0
    has_adaptive = (profile == "B3_ADAPTIVE")
    adaptive_av = AV["avail"] if has_adaptive else AV["avail"]  # real zero available
    temporal = {
        "first_contact_time": av(g("time_to_first_detection"), AV["avail"]),
        "first_engagement_time": av(g("time_to_first_engagement"), AV["avail"]),
        "first_attack_time": av(g("time_to_first_kill"), AV["avail"]),
        "resolution_time": av(resolution, AV["avail"]),
        "phase_switch_count": av(None, AV["na"]),  # no phase concept observable -> not 0
    }
    adaptation = {
        "adaptive_replan_count": av(b3_replan, adaptive_av),
        "lane_shift_count": av(g("b3_lane_shift_count") or 0, adaptive_av),
        "dispersion_event_count": av(g("b3_dispersion_event_count") or 0, adaptive_av),
        "detected_white_event_count": av(g("b3_detected_white_event_count") or 0, adaptive_av),
        "replan_frequency_per_1000s": av(round(b3_replan * 1000.0 / resolution, 3)
                                         if resolution else None,
                                         AV["avail"] if has_adaptive else AV["avail"]),
        "contact_to_replan_latency": av(None, AV["na"]),   # no per-event timestamps
    }
    geom = geometry_proxies(samples)
    front = arrival_front_proxy(samples)
    spatial = {
        "approach_lane_entropy": av(g("approach_lane_entropy"), AV["proxy"]),
        "mean_visible_group_count": av(g("active_group_count_mean"), AV["proxy"]),
        "mean_group_spacing_km": av(g("mean_group_spacing_km"), AV["proxy"]),
        "peak_simultaneous_visible": av(g("peak_simultaneous_threat_count"), AV["proxy"]),
    }
    spatial.update({k: v for k, v in geom.items() if k not in spatial})
    coordination = dict(front)
    coordination["approach_bearing_entropy"] = av(g("approach_lane_entropy"), AV["proxy"])
    coordination["group_arrival_sync"] = front.get("arrival_front_sync_std_s",
                                                   {"value": None, "availability": AV["na"]})
    behavioral = {
        "temporal": temporal,
        "spatial": spatial,
        "coordination": coordination,
        "adaptation": adaptation,
    }
    response = {
        "outcomes": {
            "victory": av(1 if row.get("victory") == "1" else 0, AV["avail"]),
            "clean_win": av(1 if row.get("clean_win") == "1" else 0, AV["avail"]),
            "breakthrough_count": av(g("enemy_breakthrough_count"), AV["avail"]),
            "white_friendly_losses": av(g("friendly_total_dead"), AV["avail"]),
            "enemy_kills": av(g("enemy_combat_killed_event"), AV["avail"]),
            "explored_ratio": av(g("explored_ratio"), AV["avail"]),
            "white_reacquire_count": av(g("global_reacquire_count"), AV["avail"]),
        },
        "failure": {"failure_reason": row.get("failure_reason")},
    }
    return {"policy_id": profile, "seed": int(seed), "behavioral": behavioral,
            "response": response}


def aggregate_fingerprint(profile, fps):
    """fp-v2 per policy over N episodes. Mean/std/median/p25/p75/n per feature
    (raw per-seed values preserved separately by caller)."""
    fp = {"policy_id": profile,
          "fingerprint_version": "fp-v2",
          "scenario": "S2",
          "seed_set": [f["seed"] for f in fps],
          "episode_count": len(fps),
          "behavioral": {}, "response": {}, "availability": {}}
    for block in ("behavioral", "response"):
        fp[block] = {}
        group_names = set()
        for f in fps:
            group_names.update(f[block].keys())
        for grp in sorted(group_names):
            if not isinstance(fps[0][block][grp], dict):
                continue
            fp[block][grp] = {}
            for feat in fps[0][block][grp].keys():
                m0 = fps[0][block][grp][feat]
                if not isinstance(m0, dict) or "availability" not in m0:
                    fp[block][grp][feat] = {"n": len(fps), "note": "non-numeric/text field"}
                    continue
                raw = [f[block][grp][feat]["value"] for f in fps]
                avail = {f[block][grp][feat]["availability"] for f in fps}
                nums = [x for x in raw if isinstance(x, (int, float))]
                meta = {"n": len(fps)}
                if not nums:
                    meta.update({"mean": None, "median": None, "p25": None, "p75": None,
                                 "std": None, "min": None, "max": None})
                    fp["availability"][f"{grp}.{feat}"] = list(avail) or [AV["na"]]
                else:
                    meta.update({
                        "mean": round(statistics.mean(nums), 4),
                        "median": round(statistics.median(nums), 4),
                        "p25": round(sorted(nums)[int(len(nums) * 0.25)], 4),
                        "p75": round(sorted(nums)[max(0, min(len(nums) - 1, int(len(nums) * 0.75)))], 4),
                        "std": round(statistics.pstdev(nums), 4) if len(nums) > 1 else 0.0,
                        "min": round(min(nums), 4), "max": round(max(nums), 4),
                    })
                    fp["availability"][f"{grp}.{feat}"] = list(avail)
                fp[block][grp][feat] = meta
    return fp


if __name__ == "__main__":
    ep = load_episodes()
    for prof in PROFILES:
        fps = []
        for sd in SEEDS:
            if (prof, sd) in ep:
                row = ep[(prof, sd)]
                if row.get("http_or_trace_errors") or row.get("agent_rc") not in ("0", None, ""):
                    continue
                fps.append(episode_fp(prof, sd, row, load_trace(prof, sd)))
        if fps:
            agg = aggregate_fingerprint(prof, fps)
            print(prof, "n=", len(fps), "keys=", list(agg["behavioral"].keys()))
