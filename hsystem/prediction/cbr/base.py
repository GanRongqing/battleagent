# -*- coding: utf-8 -*-
"""CaseRetriever — EXTENSION POINT ONLY (not implemented).

Future: retrieve similar historical maneuvers to seed the PredictorManager. Any implementation MUST use
only legal observation-derived features (no hidden Black truth).
"""
from abc import ABC, abstractmethod


class CaseRetriever(ABC):
    @abstractmethod
    def retrieve(self, trajectory_features, top_k=5):
        """Return a list of TrajectoryCase (similar historical maneuvers)."""
        raise NotImplementedError
