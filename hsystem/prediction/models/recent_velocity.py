# -*- coding: utf-8 -*-
"""RecentVelocityPredictor — robust recent velocity (reduces single-step noise/stale estimate)."""
from ..base import MotionPredictor
from ..prediction import Prediction


class RecentVelocityPredictor(MotionPredictor):
    name = "recent_velocity"

    def predict(self, history, horizon_s):
        now = history.latest()
        if now is None:
            return Prediction(self.name, horizon_s, 0.0, 0.0, 0.0, 0.0)
        t, x, y = now
        vx, vy = history.recent_velocity(3)
        px, py = x + vx * horizon_s, y + vy * horizon_s
        unc = 400.0 + 28.0 * horizon_s
        return Prediction(self.name, horizon_s, px, py, unc, 0.75, [vx, vy])
