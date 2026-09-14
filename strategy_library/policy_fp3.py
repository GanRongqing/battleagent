#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""policy_fp3.py — generic phase/role structural features (fp-v3).

Uniformly computable for B0/B1/B2/B3 and the auto candidate from the *actual
initial Black waypoint plans* (pure functions of seed + geometry) plus, where a
phase controller exists, its offline event counters.

These are generic definitions (not candidate-only):
  reserve_fraction              fraction of ships that hold near the east edge early
  early_force_commitment_ratio  fraction committing west early
  late_force_commitment_ratio   fraction committing west by end of plan
  early_late_concentration_delta
  role_asymmetry_index          dispersion of per-ship early commitment progress
  dominant_axis_shift_count     whether the committed mass shifts lateral axis
  main_force_commit_time        0 for no-reserve policies; from events otherwise
  phase_switch_count            discrete controller phase transitions (0 if none)
"""
import math
import statistics

ENEMY_X = 260000.0
BREAK_X = 50000.0
Y_LO, Y_HI = 180000.0, 600000.0
SPAN = ENEMY_X - BREAK_X

FP3_VERSION = "fp-v3"


def _min_x(pts):
    return min(p[0] for p in pts) if pts else None


def _y_at_min_x(pts):
    return min(pts, key=lambda p: p[0])[1] if pts else None


def plan_features(paths):
    """Compute generic structural features from a list of waypoint chains."""
    n = len(paths)
    if n == 0:
        return {}
    early_x, late_x, held, progress = [], [], [], []
    for path in paths:
        if not path:
            continue
        k = max(1, int(math.ceil(0.4 * len(path))))
        ex = _min_x(path[:k])
        lx = _min_x(path)
        early_x.append(ex); late_x.append(lx)
        held.append(1.0 if ex > ENEMY_X - 0.15 * SPAN else 0.0)
        progress.append((ENEMY_X - ex) / SPAN)
    if not early_x:
        return {}
    early_ratio = sum(1 for x in early_x if x < ENEMY_X - 0.4 * SPAN) / len(early_x)
    late_ratio = sum(1 for x in late_x if x < ENEMY_X - 0.4 * SPAN) / len(late_x)
    mean_prog = statistics.mean(progress) if progress else 0.0
    role_asym = (statistics.pstdev(progress) / (mean_prog + 1e-9)) if len(progress) > 1 else 0.0
    early_committed_ys = [_y_at_min_x(paths[i][:max(1, int(math.ceil(0.4 * len(paths[i]))))])
                          for i in range(n)
                          if paths[i] and early_x[i] < ENEMY_X - 0.4 * SPAN]
    late_ys = [_y_at_min_x(paths[i]) for i in range(n) if paths[i]]
    axis_shift = 0
    if early_committed_ys and late_ys:
        shift = abs(statistics.median(late_ys) - statistics.median(early_committed_ys))
        axis_shift = 1 if shift > 0.25 * (Y_HI - Y_LO) else 0
    return {
        "reserve_fraction": round(sum(held) / len(held), 4),
        "early_force_commitment_ratio": round(early_ratio, 4),
        "late_force_commitment_ratio": round(late_ratio, 4),
        "early_late_concentration_delta": round(late_ratio - early_ratio, 4),
        "role_asymmetry_index": round(role_asym, 4),
        "dominant_axis_shift_count": int(axis_shift),
    }


def with_events(feat, events=None):
    """Attach controller-derived features (true zero when no phase controller)."""
    ev = events or {}
    feat = dict(feat)
    feat["phase_switch_count"] = int(ev.get("phase_switch_count", 0) or 0)
    feat["main_force_commit_time"] = (ev.get("main_commit_time")
                                      if ev.get("main_commit_time") is not None else 0.0)
    return feat
