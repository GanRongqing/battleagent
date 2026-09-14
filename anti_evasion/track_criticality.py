# -*- coding: utf-8 -*-
"""anti_evasion/track_criticality.py — TrackCriticality (UAV track maintenance).

W6 Module 3: prioritize TRACK_MAINTENANCE for high-uncertainty, high-breakthrough-risk,
low-redundancy tracks (instead of always exploring distant new areas).

criticality (0..1) from:
  breakthrough risk   (weight)
  uncertainty         (weight)
  uncertainty growth / maneuver (weight)
  redundancy deficit (fewer sensors on the track -> higher criticality)
"""
from . import config as cfg


def criticality(track, now, sensor_support_count=0,
                break_weight=cfg.CRIT_BREAK_WEIGHT,
                uncert_weight=cfg.CRIT_UNCERT_WEIGHT,
                man_weight=cfg.CRIT_MANEUVER_WEIGHT,
                red_weight=cfg.CRIT_REDUNDANCY_WEIGHT):
    pos = track.predicted_position(now) if hasattr(track, "predicted_position") else None
    # breakthrough component (0..1)
    brk = 0.0
    if pos is not None:
        x = pos[0]
        vx = track.last_velocity[0] if getattr(track, "last_velocity", None) else 0.0
        prox = max(0.0, 1.0 - (x - cfg.BREAK_X) / 200_000.0)
        vel = max(0.0, min(1.0, -vx / 20.0))
        brk = 0.7 * prox + 0.3 * vel
    # uncertainty component (0..1), normalized by a "decision-quality" scale
    unc = track.uncertainty(now) if hasattr(track, "uncertainty") else 4000.0
    unc_norm = min(1.0, unc / 30_000.0)
    man = float(getattr(track, "maneuver_score", 0.0) or 0.0)
    # redundancy deficit: 0 sensors -> 1, many sensors -> 0
    red_def = 1.0 / (1.0 + sensor_support_count)
    c = (break_weight * brk + uncert_weight * unc_norm
         + man_weight * min(1.0, man) + red_weight * red_def)
    denom = break_weight + uncert_weight + man_weight + red_weight
    return max(0.0, min(1.0, c / denom))


def is_high_criticality(crit, threshold=cfg.HIGH_CRIT):
    return crit >= threshold
