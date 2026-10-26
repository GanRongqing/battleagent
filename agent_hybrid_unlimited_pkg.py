#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""agent_hybrid_unlimited_pkg.py — C24: UNLIMITED_PACKAGES (diagnostic for Q7).

Parent: C19 (agent_hybrid_press_search.py). Candidate: white-combat-0024-v1.

E23 lock-chain audit: White starts only 11 lock chains (10 hits, 4 kills at 11221 s) vs Black's 67
chains / 40 hits / first kills at 10707 s. The C10 BudgetGate caps total synchronized packages at 3.
This candidate removes the package budget (MAX_TOTAL_PACKAGES large) on top of C19, to test directly
whether the coordination budget is the limiting factor. Everything else is C19.
"""
import sys

import agent_hybrid_budget_gate as _bg

_bg.MAX_TOTAL_PACKAGES = 10 ** 9          # effectively unlimited (diagnostic)

from agent_hybrid_press_search import PressSearchAgentMain, PressSearchController  # noqa: E402

POLICY_ID = "white-combat-0024-v1"
PARENT = "C19(white-combat-0019-v1)"
MECHANISM = "UNLIMITED_PACKAGES"


class UnlimitedPkgController(PressSearchController):
    pass


class UnlimitedPkgAgentMain(PressSearchAgentMain):
    def __init__(self, use_uavs=True, max_steps=40000):
        super().__init__(use_uavs=use_uavs, max_steps=max_steps)
        self.usv_ctrl = UnlimitedPkgController()


if __name__ == "__main__":
    use_uavs = True
    for a in sys.argv[1:]:
        if a == "--no-uav":
            use_uavs = False
    UnlimitedPkgAgentMain(use_uavs=use_uavs).run()
