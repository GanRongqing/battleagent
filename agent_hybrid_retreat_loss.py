#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""agent_hybrid_retreat_loss.py — C20: STOP_PRESS_AFTER_LOSS.

Parent: C19 (agent_hybrid_press_search.py). Candidate: white-combat-0020-v1.

Hypothesis (H2, E21): C19's unconditional eastward press produced W2-1's first kills but made every
scenario lose all 20 USVs (over-commitment/suicide). A risk-averse rule — press east to gain contact, but
once a friendly USV is lost, stop pressing and fall back to the conservative fixed screen — should limit
losses while keeping early kills.

Mechanism (ONE): after the first observed friendly loss, revert the GLOBAL_REACQUIRE no-target movement
from "press east" back to the C10 fixed-screen behaviour. All else is C19/C10.
"""
import sys

from agent_hybrid_press_search import PressSearchAgentMain, PressSearchController

POLICY_ID = "white-combat-0020-v1"
PARENT = "C19(white-combat-0019-v1)"
MECHANISM = "STOP_PRESS_AFTER_LOSS"


class StopPressAfterLossController(PressSearchController):
    def __init__(self):
        super().__init__()
        self._lost = False

    def step(self, obs, tracks, legal, alloc_result, events, intent=None, mission=None):
        if any(not u.get("is_alive") for u in obs.usvs):
            self._lost = True
        return super().step(obs, tracks, legal, alloc_result, events, intent, mission)

    def _screen_redirect(self, pos, target_pos):
        if self._lost:
            return target_pos
        return super()._screen_redirect(pos, target_pos)


class StopPressAfterLossAgentMain(PressSearchAgentMain):
    def __init__(self, use_uavs=True, max_steps=40000):
        super().__init__(use_uavs=use_uavs, max_steps=max_steps)
        self.usv_ctrl = StopPressAfterLossController()


if __name__ == "__main__":
    use_uavs = True
    for a in sys.argv[1:]:
        if a == "--no-uav":
            use_uavs = False
    StopPressAfterLossAgentMain(use_uavs=use_uavs).run()
