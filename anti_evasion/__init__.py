# -*- coding: utf-8 -*-
"""anti_evasion — W6 Anti-Evasion / Predictive-Interception harness layer.

Observation-driven deterministic capability on top of the frozen V5 harness.
Feature-gated: every module can be independently enabled/disabled for ablation.
W5 behavior is fully restored when W6_ANTI_EVASION=0 (or all features off).

NO opponent-profile / count / seed / scenario branch. NO hidden truth.
"""
from .config import (W6_ENABLED, feature_on,  # noqa: F401
                     PREDICTIVE_INTERCEPT, PURSUIT_COST, HANDOFF,
                     UAV_TRACK_MAINTENANCE, ADAPTIVE_SCREEN,
                     BREAKTHROUGH_HORIZON)
