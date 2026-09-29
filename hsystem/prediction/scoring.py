# -*- coding: utf-8 -*-
"""Online scoring — EMA of prediction error per model, updated on legal re-observation.

No hidden truth: scores update only when a NEW LEGAL observation of the target arrives.
"""


class OnlineScorer:
    def __init__(self, alpha=0.3):
        self.alpha = alpha
        self.ema = {}      # model_id -> EMA error
        self.count = {}    # model_id -> n updates

    def update(self, model_id, error):
        prev = self.ema.get(model_id)
        self.ema[model_id] = error if prev is None else (self.alpha * error + (1 - self.alpha) * prev)
        self.count[model_id] = self.count.get(model_id, 0) + 1

    def score(self, model_id, default=1e9):
        return self.ema.get(model_id, default)

    def has_evidence(self, model_id, min_n=2):
        return self.count.get(model_id, 0) >= min_n
