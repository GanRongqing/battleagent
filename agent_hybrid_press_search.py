#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""agent_hybrid_press_search.py — C19: PRESS_ON_CONTACT_LOSS.

Parent: C10 (agent_hybrid_budget_gate.py). Candidate: white-combat-0019-v1.

Hypothesis (E21 P0): in W2-1 the fleet advances to x~204 km at ~2 h (where the brief 01:53 contact
occurs), then loses the ship track -> mission flips to GLOBAL_REACQUIRE -> no-target USVs converge to the
fixed defensive screen `SCREEN_X=120 km` and stay pinned for 4+ h, never re-closing on the Black. In W2-4
(which keeps contact) the fleet advances to x~297 km. The retreat-to-screen after contact loss is the
behavioural divergence that prevents re-acquisition.

Mechanism (ONE, minimal): in GLOBAL_REACQUIRE with no assigned target, instead of converging to the fixed
`SCREEN_X`, **keep pressing east** (same 100 km east step as the normal patrol). This preserves the
aggressive search intent after a contact is lost. All locking/allocator/UAV/sensor logic is unchanged.
No scenario/route/strategy ID, no truth, no black-state read.
"""
import sys

from agent_hybrid_budget_gate import BudgetGateAgentMain, BudgetGateController
from agent_hybrid_v5 import SCREEN_X

POLICY_ID = "white-combat-0019-v1"
PARENT = "C10(white-combat-0010-v1)"
MECHANISM = "PRESS_ON_CONTACT_LOSS"
ADVANCE_STEP = 100_000.0


class PressSearchController(BudgetGateController):
    def _is_screen_move(self, pos, target_pos):
        return (pos is not None and target_pos is not None
                and abs(target_pos[0] - SCREEN_X) < 1.0
                and abs(target_pos[1] - pos[1]) < 1.0)

    def _screen_redirect(self, pos, target_pos):
        if self._is_screen_move(pos, target_pos):
            return (pos[0] + ADVANCE_STEP, pos[1])
        return target_pos

    def _move(self, name, pos, target_pos):
        return super()._move(name, pos, self._screen_redirect(pos, target_pos))


class PressSearchAgentMain(BudgetGateAgentMain):
    def __init__(self, use_uavs=True, max_steps=40000):
        super().__init__(use_uavs=use_uavs, max_steps=max_steps)
        self.usv_ctrl = PressSearchController()


if __name__ == "__main__":
    use_uavs = True
    for a in sys.argv[1:]:
        if a == "--no-uav":
            use_uavs = False
    PressSearchAgentMain(use_uavs=use_uavs).run()
