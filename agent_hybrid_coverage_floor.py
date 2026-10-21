#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""agent_hybrid_coverage_floor.py — C14: COVERAGE_FLOOR_SCREEN.

Parent: C10 (agent_hybrid_budget_gate.py). Candidate: white-combat-0014-v1.

Problem (E13 diagnosis, W2-5): the surviving White USVs drift into a one-sided (southern) cluster while
the final Black dash uses both flanks (usv10 y≈+55 km, usv21 y≈−55 km). With every available USV holding
its own (southern) y, the northern flank is uncovered and Black breaches.

Mechanism (ONE, minimal): during MISSION_GLOBAL_REACQUIRE, instead of each available USV holding its own y,
spread the available USVs across the fleet's **own initial y-band** (recorded from the first observation,
a legal own-history quantity) so both flanks stay covered. No scenario/route/strategy ID, no truth.
All other behaviour is identical to C10.
"""
import sys

from agent_hybrid_budget_gate import BudgetGateAgentMain, BudgetGateController
from agent_hybrid_v5 import MISSION_GLOBAL_REACQUIRE

POLICY_ID = "white-combat-0014-v1"
PARENT = "C10(white-combat-0010-v1)"
MECHANISM = "COVERAGE_FLOOR_SCREEN"


class CoverageFloorController(BudgetGateController):
    def __init__(self):
        super().__init__()
        self._init_y = []

    def _record_initial(self, obs):
        if self._init_y:
            return
        ys = [u["position"][1] for u in obs.usvs if u.get("position")]
        if ys:
            self._init_y = sorted(ys)

    def step(self, obs, tracks, legal, alloc_result, events, intent=None, mission=None):
        self._record_initial(obs)
        actions = super().step(obs, tracks, legal, alloc_result, events, intent, mission)
        if mission != MISSION_GLOBAL_REACQUIRE or not self._init_y:
            return actions
        # available (no target) alive USVs, deterministic order
        avail = [u for u in obs.usvs if u.get("is_alive") and u.get("position")
                 and not self.targets.get(u["name"]) and self.state.get(u["name"]) == self.AVAILABLE]
        if not avail:
            return actions
        avail.sort(key=lambda u: u["name"])
        n = len(avail)
        # spread target y across the fleet's own initial band (both flanks)
        if n == 1:
            tgt_ys = [0.0]
        else:
            lo, hi = self._init_y[0], self._init_y[-1]
            tgt_ys = [lo + (hi - lo) * i / (n - 1) for i in range(n)]
        from agent_hybrid_v5 import SCREEN_X
        pos = {u["name"]: (u["position"][0], u["position"][1]) for u in avail}
        for u, ty in zip(avail, tgt_ys):
            nm = u["name"]
            actions = [a for a in actions if a[0].split(" ", 1)[0] != nm]
            actions.append(self._move(nm, pos[nm], (SCREEN_X, ty)))
        return actions


class CoverageFloorAgentMain(BudgetGateAgentMain):
    def __init__(self, use_uavs=True, max_steps=40000):
        super().__init__(use_uavs=use_uavs, max_steps=max_steps)
        self.usv_ctrl = CoverageFloorController()


if __name__ == "__main__":
    use_uavs = True
    for a in sys.argv[1:]:
        if a == "--no-uav":
            use_uavs = False
    CoverageFloorAgentMain(use_uavs=use_uavs).run()
