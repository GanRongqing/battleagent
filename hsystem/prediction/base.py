# -*- coding: utf-8 -*-
"""MotionPredictor — pluggable prediction interface.

A predictor may ONLY use: legal observation, TrackManager-maintained history (positions/times),
estimated velocity/heading/turn, prediction-error history. It MUST NOT read Black future waypoints,
true future positions, scenario routes, or hidden engine state.
"""
from abc import ABC, abstractmethod

from .prediction import Prediction


class MotionPredictor(ABC):
    name = "abstract"

    @abstractmethod
    def predict(self, history, horizon_s) -> Prediction:
        """history: TrackHistory (legal samples). Returns a Prediction at now+horizon_s."""
        raise NotImplementedError
