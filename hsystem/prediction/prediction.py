# -*- coding: utf-8 -*-
"""Prediction — unified output of any MotionPredictor."""
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class Prediction:
    model_id: str
    horizon_s: float
    position_x: float
    position_y: float
    uncertainty_radius: float = 0.0
    confidence: float = 0.0
    velocity: Optional[List[float]] = None
    heading: Optional[float] = None
    region: Optional[List[List[float]]] = None
    metadata: dict = field(default_factory=dict)

    def distance_to(self, x, y):
        return ((self.position_x - x) ** 2 + (self.position_y - y) ** 2) ** 0.5
