# -*- coding: utf-8 -*-
"""anti_evasion/breakthrough_risk.py — BreakthroughRiskEstimator.

W6 Module 5: deadline-aware risk.

risk is high when the target's expected time to reach the break line
is LESS than the best available interceptor's ETA (+ safety margin) —
i.e. nobody can realistically stop it in time.

Uses only legal track belief + intercept plans. No hidden future path.
"""
import math

from . import config as cfg


class BreakthroughRisk:
    __slots__ = ("track_name", "breakthrough_eta", "best_interceptor_eta",
                 "interceptor_deficit", "risk_score")

    def __init__(self, track_name, b_eta, i_eta, deficit, risk):
        self.track_name = track_name
        self.breakthrough_eta = b_eta
        self.best_interceptor_eta = i_eta
        self.interceptor_deficit = deficit
        self.risk_score = risk

    def to_dict(self):
        return {"track_name": self.track_name,
                "breakthrough_eta": round(self.breakthrough_eta, 1),
                "best_interceptor_eta": (round(self.best_interceptor_eta, 1)
                                         if self.best_interceptor_eta is not None else None),
                "interceptor_deficit": round(self.interceptor_deficit, 1),
                "risk_score": round(self.risk_score, 3)}


class BreakthroughRiskEstimator:
    def __init__(self, break_x=cfg.BREAK_X, safety=cfg.SCREEN_ETA_SAFETY):
        self.break_x = break_x
        self.safety = safety

    def estimate(self, track, now, corridors, intercept_plans):
        pos = track.predicted_position(now) if hasattr(track, "predicted_position") else None
        if pos is None or pos[0] <= self.break_x:
            return BreakthroughRisk(getattr(track, "name", "?"), 0.0, 0.0, 0.0, 1.0)
        vel = track.last_velocity or [0.0, 0.0]
        vx = vel[0]
        dist_to_break = pos[0] - self.break_x
        if vx >= 0:
            # moving away (or static): still exposed if far from cover, but no imminent deadline
            b_eta = float("inf")
        else:
            b_eta = dist_to_break / (-vx)
        # best interceptor ETA from the intercept plans
        corr = corridors.get(getattr(track, "name", "")) if corridors else None
        i_eta = None
        if intercept_plans:
            plan = intercept_plans.get(getattr(track, "name", ""))
            if plan is not None:
                i_eta = plan.intercept_eta
        deficit = None
        if b_eta != float("inf") and i_eta is not None:
            deficit = b_eta - i_eta * (1.0 + self.safety)
        # risk score (0..1)
        if b_eta == float("inf"):
            risk = 0.0
        elif i_eta is None:
            risk = 1.0   # nobody assigned/interceptable -> maximal exposure
        else:
            denom = max(1.0, b_eta)
            risk = max(0.0, min(1.0, (1.0 - (i_eta * (1.0 + self.safety)) / denom)))
        return BreakthroughRisk(getattr(track, "name", "?"), b_eta, i_eta, deficit, risk)
