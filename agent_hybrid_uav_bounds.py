#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""agent_hybrid_uav_bounds.py — C17: UAV_AREA_BOUNDED_FLIGHT.

Parent: C10 (agent_hybrid_budget_gate.py). Candidate: white-combat-0017-v1.

Verified defect (E18 P1): in W2-1 all 10 White UAVs drift to the northern operational-area edge
(y ≈ 276–277 km vs area limit 277.8 km) and are removed by the judge's area-out rule at ~9.6–11.8 ks,
before any engagement — leaving White without forward sensors → zero own lock/kills.

Mechanism (ONE, minimal): bound every UAV flight waypoint's y to the fleet's **own initial y extent**
(recorded at the first observation, legal own-history) + a small margin. This keeps search/screen/
reacquire flights inside the operational area without hard-coding any scenario/route/strategy or reading
truth. x uses the existing world bounds. All other UAV/USV/allocator/lock logic unchanged.
"""
import sys

from agent_hybrid_budget_gate import BudgetGateAgentMain
from agent_hybrid_v5 import UAVManager

POLICY_ID = "white-combat-0017-v1"
PARENT = "C10(white-combat-0010-v1)"
MECHANISM = "UAV_AREA_BOUNDED_FLIGHT"
Y_MARGIN = 10_000.0


class BoundedUAVManager(UAVManager):
    def __init__(self, enabled=True):
        super().__init__(enabled=enabled)
        self._y_limit = None

    def step(self, obs, tracker, legal, events, intent=None, threat_fn=None, coverage=None, mission=None):
        if self._y_limit is None:
            ys = [abs(u["position"][1]) for u in (obs.uavs or []) + (obs.usvs or [])
                  if u.get("position")]
            if ys:
                self._y_limit = max(ys) + Y_MARGIN
        return super().step(obs, tracker, legal, events, intent, threat_fn, coverage, mission)

    def _fly(self, name, pos, target_pos):
        if target_pos is not None and self._y_limit:
            y = max(-self._y_limit, min(self._y_limit, target_pos[1]))
            target_pos = (target_pos[0], y)
        return super()._fly(name, pos, target_pos)


class BoundedUAVAgentMain(BudgetGateAgentMain):
    def __init__(self, use_uavs=True, max_steps=40000):
        super().__init__(use_uavs=use_uavs, max_steps=max_steps)
        self.uav_mgr = BoundedUAVManager(enabled=use_uavs)


if __name__ == "__main__":
    use_uavs = True
    for a in sys.argv[1:]:
        if a == "--no-uav":
            use_uavs = False
    BoundedUAVAgentMain(use_uavs=use_uavs).run()
