#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""agent_hybrid_c31.py — C31: C30 + scenario-agnostic (public-polygon) Boundary Safety.

Parent: C30 (agent_hybrid_split_screen.py). Candidate: white-combat-0031-v1.
Only the boundary-safety region source changes (hardcoded W2 rectangle -> real public operational polygon).
All tactics (press / UAV tether / split screen / allocator) are unchanged from C30.
"""
import sys
import os
import atexit
import json

from agent_hybrid_split_screen import SplitScreenAgentMain
from scenario_agnostic_safety import ScenarioAgnosticBoundarySafety

POLICY_ID = "white-combat-0031-v1"
PARENT = "C30(white-combat-0030-v1)"
MECHANISM = "SCENARIO_AGNOSTIC_BOUNDARY_SAFETY"


class C31AgentMain(SplitScreenAgentMain):
    def __init__(self, use_uavs=True, max_steps=40000):
        super().__init__(use_uavs=use_uavs, max_steps=max_steps)
        self.safety = ScenarioAgnosticBoundarySafety()
        if os.environ.get("SAFETY_TRACE"):
            atexit.register(self._dump_safety)

    def _dump_safety(self):
        try:
            with open(os.environ["SAFETY_TRACE"], "a", encoding="utf-8") as f:
                f.write(json.dumps({"available": self.safety.available,
                                    "rewrites": self.safety.area_rewrites,
                                    "predicted_out": self.safety.predicted_out_rewrites,
                                    "unneeded": self.safety.unnecessary_rewrites,
                                    "current_out": self.safety.current_out_rewrites,
                                    "preventive": self.safety.preventive_buffer_rewrites,
                                    "unexpected": self.safety.unexpected_rewrites,
                                    "reason": self.safety.unavailable_reason}) + "\n")
        except Exception:
            pass


if __name__ == "__main__":
    use_uavs = True
    for a in sys.argv[1:]:
        if a == "--no-uav":
            use_uavs = False
    C31AgentMain(use_uavs=use_uavs).run()
