# -*- coding: utf-8 -*-
"""anti_evasion/motion_predictor.py — ShortHorizonPredictor + PredictedCorridor.

W6 Module 1: Predictive Interception.

Produces a PREDICTED CORRIDOR (center + dynamic radius), NOT a single exact future point.
The prediction horizon shrinks with:
  - lower point-confidence / older observation
  - larger current uncertainty
  - higher maneuver evidence (heading oscillation / velocity change)

All inputs are legal TrackManager belief fields. No hidden truth.
"""
import math

from . import config as cfg


class PredictedCorridor:
    __slots__ = ("track_name", "current_estimate", "predicted_position",
                 "prediction_horizon_s", "prediction_uncertainty", "motion_confidence",
                 "velocity")

    def __init__(self, track_name, current_estimate, predicted_position, horizon_s,
                 uncertainty, motion_confidence, velocity):
        self.track_name = track_name
        self.current_estimate = current_estimate
        self.predicted_position = predicted_position
        self.prediction_horizon_s = horizon_s
        self.prediction_uncertainty = uncertainty
        self.motion_confidence = motion_confidence
        self.velocity = velocity

    def to_dict(self):
        return {"track_name": self.track_name,
                "current_estimate": list(self.current_estimate) if self.current_estimate else None,
                "predicted_position": list(self.predicted_position) if self.predicted_position else None,
                "prediction_horizon_s": round(self.prediction_horizon_s, 1),
                "prediction_uncertainty": round(self.prediction_uncertainty, 1),
                "motion_confidence": round(self.motion_confidence, 3)}


class ShortHorizonPredictor:
    """Constant-velocity extrapolation with maneuver-aware confidence decay.

    Horizon rule (normalized, no fleet/count/opponent dependence):
      horizon = PRED_BASE_HORIZON_S * motion_confidence, clamped to [PRED_MIN_HORIZON_S, base]
      motion_confidence = base_confidence * (1 - maneuver_penalty) * age_penalty
    """

    def __init__(self, base_horizon=cfg.PRED_BASE_HORIZON_S,
                 min_horizon=cfg.PRED_MIN_HORIZON_S,
                 uncert_growth=cfg.UNCERT_GROWTH, maneuver_uncert=cfg.MANEUVER_UNCERT):
        self.base_horizon = base_horizon
        self.min_horizon = min_horizon
        self.uncert_growth = uncert_growth
        self.maneuver_uncert = maneuver_uncert

    def predict(self, track, now):
        """track: an object with the TrackManager belief fields (or a dict-like).

        Uses: last_position, last_velocity, point_confidence, maneuver_score,
        uncertainty(now), age(now), is_visible(now)."""
        pos = _get(track, "last_position") or _get(track, "position")
        vel = _get(track, "last_velocity") or [0.0, 0.0]
        if pos is None or len(pos) < 2:
            return None
        name = _get(track, "name", "?")
        pc = float(_get(track, "point_confidence", 0.5) or 0.5)
        man = float(_get(track, "maneuver_score", 0.0) or 0.0)
        age = _age(track, now)
        unc = _uncertainty(track, now)

        # motion confidence: base point-confidence, discounted by maneuver and age
        man_penalty = min(1.0, man)
        age_penalty = min(1.0, age / 300.0)          # 300s -> fully age-discounted
        motion_confidence = max(0.05, pc * (1.0 - man_penalty) * (1.0 - 0.5 * age_penalty))

        # dynamic horizon
        horizon = self.base_horizon * motion_confidence
        horizon = max(self.min_horizon, min(self.base_horizon, horizon))

        # predicted corridor
        px = pos[0] + vel[0] * horizon
        py = pos[1] + vel[1] * horizon
        pred_unc = unc + self.uncert_growth * horizon + self.maneuver_uncert * man
        return PredictedCorridor(name, (pos[0], pos[1]), (px, py), horizon, pred_unc,
                                 motion_confidence, (vel[0], vel[1]))

    def predict_all(self, tracks, now):
        out = {}
        for name, t in tracks.items():
            c = self.predict(t, now)
            if c is not None:
                out[name] = c
        return out


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        return default
    if hasattr(obj, key):
        v = getattr(obj, key)
        if callable(v):
            return default
        return v
    return default


def _age(track, now):
    v = _get(track, "age")
    if v is not None:
        return float(v)
    if hasattr(track, "age"):
        try:
            return float(track.age(now))
        except Exception:
            pass
    last = _get(track, "last_seen_time")
    return max(0.0, now - float(last)) if last is not None else 0.0


def _uncertainty(track, now):
    v = _get(track, "uncertainty")
    if v is not None:
        return float(v)
    if hasattr(track, "uncertainty"):
        try:
            return float(track.uncertainty(now))
        except Exception:
            pass
    base = 4000.0
    return base + cfg.UNCERT_GROWTH * _age(track, now)
