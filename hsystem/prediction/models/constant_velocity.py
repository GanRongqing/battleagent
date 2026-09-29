# -*- coding: utf-8 -*-
"""ConstantVelocityPredictor — p(t+D) = p(t) + v*D."""
from ..base import MotionPredictor
from ..prediction import Prediction


class ConstantVelocityPredictor(MotionPredictor):
    name = "constant_velocity"

    def predict(self, history, horizon_s):
        now = history.latest()
        if now is None:
            return Prediction(self.name, horizon_s, 0.0, 0.0, 0.0, 0.0)
        t, x, y = now
        vx, vy = history.velocity()
        px, py = x + vx * horizon_s, y + vy * horizon_s
        unc = 500.0 + 30.0 * horizon_s
        return Prediction(self.name, horizon_s, px, py, unc, 0.8, [vx, vy])
