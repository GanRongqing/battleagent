#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""agent_hybrid_split_screen.py — C30: UNIT_LEVEL_SPLIT_SCREEN (+ UAV safety).

Parent: C27 (agent_hybrid_safe_recon.py). Candidate: white-combat-0030-v1.

E26 P0: every C27 Defeat is a Black breakthrough (1-3 ships reach x<=50 km). White no-target USVs all press
east, leaving the western breakthrough line uncovered, so breachers slip past. Fix (ONE, unit-level): split
the no-target fleet by stable unit index — ~1/3 hold a defensive screen at SCREEN_X (guard the breakthrough
line), the rest keep pressing east to engage. Engaged/locking units untouched; universal safety (USV+UAV)
still applies. No scenario ID/seed/route; unit role by name index only.
"""
import sys

from agent_hybrid_press_search import PressSearchController
from agent_hybrid_safe_recon import SafeReconAgentMain
from agent_hybrid_v5 import SCREEN_X
from adaptive_skills import AREA

POLICY_ID = "white-combat-0030-v1"
PARENT = "C27(white-combat-0027-v1)"
MECHANISM = "UNIT_LEVEL_SPLIT_SCREEN"
SCREEN_EVERY = 3


class SplitScreenController(PressSearchController):
    @staticmethod
    def _is_screen_unit(name):
        try:
            idx = int(name.replace("white_usv", ""))
        except Exception:
            return False
        return idx % SCREEN_EVERY == 0

    def step(self, obs, tracks, legal, alloc_result, events, intent=None, mission=None):
        actions = super().step(obs, tracks, legal, alloc_result, events, intent, mission)
        pos = {u["name"]: (u["position"][0], u["position"][1]) for u in obs.usvs
               if u.get("is_alive") and u.get("position")}
        for name, p in pos.items():
            if self.targets.get(name):
                continue
            if self.state.get(name) == self.LOCKING:
                continue
            if not self._is_screen_unit(name):
                continue
            actions = [a for a in actions if a[0].split(" ", 1)[0] != name]
            actions.append(self._move(name, p, (SCREEN_X, p[1])))
        return actions


class SplitScreenAgentMain(SafeReconAgentMain):
    def __init__(self, use_uavs=True, max_steps=40000):
        super().__init__(use_uavs=use_uavs, max_steps=max_steps)
        self.usv_ctrl = SplitScreenController()


if __name__ == "__main__":
    use_uavs = True
    for a in sys.argv[1:]:
        if a == "--no-uav":
            use_uavs = False
    SplitScreenAgentMain(use_uavs=use_uavs).run()
