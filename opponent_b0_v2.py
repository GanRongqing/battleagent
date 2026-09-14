#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""opponent_b0_v2.py — black-b0-v2 (variable-speed random baseline).

Same random-waypoint, uncoordinated, non-adaptive doctrine as B0-v1; the ONLY
change is a legal episode-level stochastic speed. B0-v1 is untouched.

Speed: episode_target_speed ~ Uniform(5.0, 10.0) m/s (audit: ShipMotorTZB.max_speed=10).
Deterministic and reproducible from the episode seed via a SEPARATE RNG stream so it
cannot perturb the waypoint RNG (which stays random.Random(seed) in scenario_builder).
"""
import random

B0_V2 = "B0_V2_VARIABLE_SPEED"
DISPLAY_NAME = "B0_RANDOM_V2_VARIABLE_SPEED"
V_MIN_OPERATIONAL = 5.0
V_MAX_OPERATIONAL = 10.0
SPEED_SALT = 0xB0B2


def sample_speed(seed, v_min=V_MIN_OPERATIONAL, v_max=V_MAX_OPERATIONAL):
    """Deterministic episode-level target speed, isolated from the waypoint RNG."""
    rng = random.Random((int(seed) * 1000003) ^ SPEED_SALT)
    return round(rng.uniform(v_min, v_max), 3)
