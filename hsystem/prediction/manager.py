# -*- coding: utf-8 -*-
"""PredictorManager — registers predictors, calls them, scores them, selects the best.

DEFAULT: shadow-only. It computes predictions and (optionally) logs them, but it does NOT feed combat
control. Activation would require PREDICTOR_LIBRARY_ACTIVE=true (future; not done here).
"""
import os

from .models.constant_velocity import ConstantVelocityPredictor
from .models.constant_turn import ConstantTurnPredictor
from .models.recent_velocity import RecentVelocityPredictor
from .scoring import OnlineScorer


class PredictorManager:
    def __init__(self):
        self.predictors = []
        self.scorer = OnlineScorer()
        self.fallback = ConstantVelocityPredictor()
        self.active = os.getenv("PREDICTOR_LIBRARY_ACTIVE", "false").lower() == "true"
        self.shadow = os.getenv("PREDICTOR_SHADOW_MODE", "true").lower() == "true"
        self.register(ConstantVelocityPredictor())
        self.register(ConstantTurnPredictor())
        self.register(RecentVelocityPredictor())

    def register(self, predictor):
        self.predictors.append(predictor)

    def predict_all(self, history, horizon_s):
        return [p.predict(history, horizon_s) for p in self.predictors]

    def select(self, history, horizon_s, min_evidence=2):
        preds = self.predict_all(history, horizon_s)
        scored = [(p, self.scorer.score(p.model_id)) for p in preds]
        with_ev = [(p, s) for p, s in scored if self.scorer.has_evidence(p.model_id, min_evidence)]
        if with_ev:
            best = min(with_ev, key=lambda ps: ps[1])[0]
            reason = "min_recent_error"
        else:
            best = self.fallback.predict(history, horizon_s)
            reason = "fallback_insufficient_evidence"
        return best, preds, reason

    def observe(self, reobserved_x, reobserved_y, prior_predictions, now):
        """Update scores using legally re-observed position vs each prior prediction whose horizon
        has elapsed. prior_predictions: [(Prediction, target_time)]."""
        for pred, target_time in prior_predictions:
            if now + 1e-6 >= target_time:
                err = pred.distance_to(reobserved_x, reobserved_y)
                self.scorer.update(pred.model_id, err)
