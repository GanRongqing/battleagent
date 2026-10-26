#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""agent_hybrid_boundary_safe.py — C26: BOUNDARY_SAFE_PRESS.

Parent: C25 (agent_hybrid_fleet_recon.py). Candidate: white-combat-0026-v1.

E24: C25 gives 13/20 W2-1 (pure combat 13/5=2.6) and pooled pure CER 1.76, BUT the eastward press runs
the fleet into the eastern area boundary and 57 USVs are removed as area-out (non-combat) across the six
scenarios. This caps official CER unnecessarily.

Mechanism (ONE): keep all C25 UAV recon, but make USV movement area-safe — clamp move targets to
x<=355 km, |y|<=265 km (inside the x=370.4, y=±277.8 area), and when already at/over the safe x, step
back west instead of pressing further east. No scenario/route ID, no truth; C25/C19 lock behaviour intact.
"""
import sys

from agent_hybrid_fleet_recon import FleetReconAgentMain
from agent_hybrid_press_search import PressSearchController

POLICY_ID = "white-combat-0026-v1"
PARENT = "C25(white-combat-0025-v1)"
MECHANISM = "BOUNDARY_SAFE_PRESS"
SAFE_X = 355_000.0
SAFE_Y = 265_000.0
FALLBACK = 30_000.0


class BoundarySafeController(PressSearchController):
    def _clamp(self, pos, target):
        if pos is None or target is None:
            return target
        tx, ty = target
        ty = max(-SAFE_Y, min(SAFE_Y, ty))
        if tx > SAFE_X:
            tx = (pos[0] - FALLBACK) if pos[0] >= SAFE_X - 1_000.0 else SAFE_X
        return (tx, ty)

    def _move(self, name, pos, target_pos):
        return super()._move(name, pos, self._clamp(pos, target_pos))


class BoundarySafeAgentMain(FleetReconAgentMain):
    def __init__(self, use_uavs=True, max_steps=40000):
        super().__init__(use_uavs=use_uavs, max_steps=max_steps)
        self.usv_ctrl = BoundarySafeController()


if __name__ == "__main__":
    use_uavs = True
    for a in sys.argv[1:]:
        if a == "--no-uav":
            use_uavs = False
    BoundarySafeAgentMain(use_uavs=use_uavs).run()
