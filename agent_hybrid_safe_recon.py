#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""agent_hybrid_safe_recon.py — C27: C25 + Universal Boundary Safety (parent C25).

Ablation C in E25: keep C25 fleet-tethered UAV recon and C19 press, but route every USV move through
BoundaryAwareSafety so self-navigation area-outs are eliminated. No tactic change.
"""
import sys

from agent_hybrid_fleet_recon import FleetReconAgentMain
from universal_safety import BoundaryAwareSafety

POLICY_ID = "white-combat-0027-v1"
PARENT = "C25(white-combat-0025-v1)"
MECHANISM = "FLEET_TETHERED_RECON+UNIVERSAL_BOUNDARY_SAFETY"


class SafeReconAgentMain(FleetReconAgentMain):
    def __init__(self, use_uavs=True, max_steps=40000):
        super().__init__(use_uavs=use_uavs, max_steps=max_steps)
        self.safety = BoundaryAwareSafety()


if __name__ == "__main__":
    use_uavs = True
    for a in sys.argv[1:]:
        if a == "--no-uav":
            use_uavs = False
    SafeReconAgentMain(use_uavs=use_uavs).run()
