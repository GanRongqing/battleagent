# -*- coding: utf-8 -*-
"""ConstantTurnPredictor — constant-turn (circular-arc) motion model.

Uses recent turn-rate evidence; if evidence is insufficient, returns low confidence and falls back to a
straight extrapolation (does not fabricate a confident turn).
"""
import math

from ..base import MotionPredictor
from ..prediction import Prediction


class ConstantTurnPredictor(MotionPredictor):
    name = "constant_turn"

    def predict(self, history, horizon_s):
        now = history.latest()
        if now is None:
            return Prediction(self.name, horizon_s, 0.0, 0.0, 0.0, 0.0)
        t, x, y = now
        vx, vy = history.velocity()
        speed = math.hypot(vx, vy)
        conf = 0.4
        if speed > 1e-3:
            h = math.atan2(vy, vx)
            omega = math.radians(history.recent_turn_rate())  # rad/s
            if abs(omega) > 1e-4:
                R = speed / omega
                dh = omega * horizon_s
                px = x + R * (math.sin(h + dh) - math.sin(h))
                py = y - R * (math.cos(h + dh) - math.cos(h))
                conf = 0.7
            else:
                px, py = x + vx * horizon_s, y + vy * horizon_s
        else:
            px, py = x, y
        unc = 500.0 + 30.0 * horizon_s + 2000.0 * (1.0 - conf)
        return Prediction(self.name, horizon_s, px, py, unc, conf, [vx, vy])
