#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""agent_hybrid_adaptive.py — C28: ADAPTIVE_SKILL_COMPOSITION (+ universal boundary safety).

Parent: C27 (agent_hybrid_safe_recon.py). Candidate: white-combat-0028-v1.

Per-axis adaptive composition driven only by legal situation features:
  - USV maneuver: ACTIVE_SEARCH (press) / DEFENSIVE_SCREEN (C10 base) / CONTACT_MAINTENANCE (targets) /
    POSITION_RECOVERY (near boundary).
  - UAV recon: FLEET_TETHERED_RECON when no live threat, BROAD_SEARCH when a threat is already tracked.
  - Engagement: existing C10 cooperative allocation / lock path (unchanged).
Every USV move still passes Universal Boundary Safety. No scenario/route/seed branching.
"""
import sys

from adaptive_skills import Composer, extract
from agent_hybrid_fleet_recon import FleetTetheredUAVManager
from agent_hybrid_press_search import PressSearchController
from agent_hybrid_safe_recon import SafeReconAgentMain
from agent_hybrid_v5 import SCREEN_X, UAVManager

POLICY_ID = "white-combat-0028-v1"
PARENT = "C27(white-combat-0027-v1)"
MECHANISM = "ADAPTIVE_SKILL_COMPOSITION"
ADVANCE_STEP = 100_000.0


class AdaptiveController(PressSearchController):
    def __init__(self):
        super().__init__()
        self.composer = Composer()
        self._mode = "ACTIVE_SEARCH"

    def step(self, obs, tracks, legal, alloc_result, events, intent=None, mission=None):
        f = extract(obs, tracks, obs.now)
        self._mode, _ = self.composer.decide(f, obs.now)
        return super().step(obs, tracks, legal, alloc_result, events, intent, mission)

    def _screen_redirect(self, pos, target_pos):
        # In ACTIVE_SEARCH keep pressing east; otherwise use C19 default (screen).
        if self._mode == "ACTIVE_SEARCH":
            if (pos is not None and target_pos is not None
                    and abs(target_pos[0] - SCREEN_X) < 1.0 and abs(target_pos[1] - pos[1]) < 1.0):
                return (pos[0] + ADVANCE_STEP, pos[1])
        return target_pos


class AdaptiveUAVManager(FleetTetheredUAVManager):
    def __init__(self, enabled=True):
        super().__init__(enabled=enabled)
        self._composer = Composer()

    def step(self, obs, tracker, legal, events, intent=None, threat_fn=None,
             coverage=None, mission=None):
        f = extract(obs, tracker.tracks, obs.now)
        _, uav_mode = self._composer.decide(f, obs.now)
        if uav_mode == "BROAD_SEARCH":
            return UAVManager.step(self, obs, tracker, legal, events, intent, threat_fn,
                                   coverage, mission)
        return super().step(obs, tracker, legal, events, intent, threat_fn, coverage, mission)


class AdaptiveAgentMain(SafeReconAgentMain):
    def __init__(self, use_uavs=True, max_steps=40000):
        super().__init__(use_uavs=use_uavs, max_steps=max_steps)
        self.usv_ctrl = AdaptiveController()
        self.uav_mgr = AdaptiveUAVManager(enabled=use_uavs)


if __name__ == "__main__":
    use_uavs = True
    for a in sys.argv[1:]:
        if a == "--no-uav":
            use_uavs = False
    AdaptiveAgentMain(use_uavs=use_uavs).run()
