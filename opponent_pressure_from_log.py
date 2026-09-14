#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""opponent_pressure_from_log.py — pressure metrics computed from API game logs.

Used for the B0 column (reused frozen formal run): the same pressure definitions that the
live collector (opponent_smoke.OpponentMetrics) uses for B3, but computed offline from the
per-step game log (White's legal radar capture). White-legal observation only.

Definitions (identical for B0/B3):
  peak_simultaneous_threat_count = max over steps of |雷达捕获 active enemies| (White-visible)
  mean_simultaneous_threat_count = mean over steps with >=1 contact
  approach_lane_entropy          = mean over steps (>=2 enemies) of lane entropy
  active_group_count_mean/peak   = mean/max over steps (>=2 enemies) of spatial-group count
  mean_group_spacing_km          = mean over steps of mean inter-group centroid distance (km)
  time_to_first_detection        = first step sim_time with >=1 active enemy
  time_to_first_engagement       = first step sim_time with any USV locking
  time_to_first_kill             = first sim_time with reward black_killed >= 1
  time_to_resolve_all_combat_threats = final step sim_time (all threats resolved / game end)
  peak/mean_active_engagements   = max/mean over steps of #locking USVs
  peak/mean_uncovered_hostile_tracks = max/mean over steps of (visible enemies not locked)
  time_with_zero_reliable_tracks = total sim-time over steps with 0 active enemies
"""
import json
import math


def _lane_entropy(ys, lane_lo, lane_hi, n_groups):
    if len(ys) < 2:
        return 0.0
    lane = [max(0, min(n_groups - 1, int((y - lane_lo) / max(1, lane_hi - lane_lo) * n_groups)))
            for y in ys]
    counts = [0] * n_groups
    for l in lane:
        counts[l] += 1
    n = len(ys)
    return -sum((c / n) * math.log2(c / n) for c in counts if c > 0)


def _spatial_groups(ys, capacity=4.0):
    order = sorted(range(len(ys)), key=lambda i: ys[i])
    cap = max(1, int(capacity))
    return [order[k:k + cap] for k in range(0, len(order), cap)]


def _group_spacing(positions):
    groups = _spatial_groups([p[1] for p in positions])
    if len(groups) < 2:
        return None
    cents = []
    for g in groups:
        xs = [positions[i][0] for i in g]
        ys = [positions[i][1] for i in g]
        cents.append((sum(xs) / len(xs), sum(ys) / len(ys)))
    total = cnt = 0
    for i in range(len(cents)):
        for j in range(i + 1, len(cents)):
            total += math.hypot(cents[i][0] - cents[j][0], cents[i][1] - cents[j][1])
            cnt += 1
    return total / cnt if cnt else None


def pressure_from_game_log(steps, enemy_total):
    n = enemy_total
    if not steps:
        return {}
    sims, active_n, lanes, groups, spacings, engag, uncover, zero_t, det_t, eng_t, kill_t = \
        [], [], [], [], [], [], [], 0.0, None, None, None
    prev_killed = 0
    peak_sim = 0
    for st in steps:
        t = float(st.get("sim_time", 0))
        sims.append(t)
        act = [e for e in (st.get("active_enemies") or [])
               if e.get("position") and len(e.get("position", [])) >= 2]
        a = len(act)
        active_n.append(a)
        peak_sim = max(peak_sim, a)
        if a > 0 and det_t is None:
            det_t = t
        locked = set()
        for u in (st.get("usv_states") or []):
            if u.get("is_locking") and u.get("locking_unit"):
                locked.add(u["locking_unit"])
                if eng_t is None:
                    eng_t = t
        engag.append(len(locked))
        uncover.append(a - len([e for e in act if e.get("name") in locked]))
        if a == 0:
            zero_t += 1  # step count with zero reliable tracks (approximation of time)
        if a >= 2:
            positions = [tuple(e["position"][:2]) for e in act]
            ys = [p[1] for p in positions]
            K = max(2, len(_spatial_groups(ys)))
            lanes.append(_lane_entropy(ys, 180000.0, 600000.0, K))
            groups.append(len(_spatial_groups(ys)))
            sp = _group_spacing(positions)
            if sp is not None:
                spacings.append(sp)
        k = int((st.get("reward") or {}).get("black_killed", 0))
        if k > 0 and prev_killed == 0 and kill_t is None:
            kill_t = t
        prev_killed = k
    last_t = sims[-1] if sims else None
    return {
        "peak_simultaneous_threat_count": peak_sim,
        "mean_simultaneous_threat_count": round(sum(active_n) / len(active_n), 2),
        "approach_lane_entropy": round(sum(lanes) / len(lanes), 4) if lanes else None,
        "active_group_count_mean": round(sum(groups) / len(groups), 1) if groups else None,
        "active_group_count_peak": max(groups) if groups else None,
        "mean_group_spacing_km": round(sum(spacings) / len(spacings) / 1000.0, 1) if spacings else None,
        "time_to_first_detection": det_t,
        "time_to_first_engagement": eng_t,
        "time_to_first_kill": kill_t,
        "time_to_resolve_all_combat_threats": last_t,
        "peak_active_engagements": max(engag) if engag else 0,
        "mean_active_engagements": round(sum(engag) / len(engag), 2) if engag else 0,
        "peak_uncovered_hostile_tracks": max(uncover) if uncover else 0,
        "mean_uncovered_hostile_tracks": round(sum(uncover) / len(uncover), 2) if uncover else 0,
        "time_with_zero_reliable_tracks_steps": zero_t,
    }
