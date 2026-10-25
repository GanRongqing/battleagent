#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""agent_hybrid_bearing_home.py — C21: PASSIVE_BEARING_HOMING.

Parent: C10 (agent_hybrid_budget_gate.py). Candidate: white-combat-0021-v1.

Hypothesis (H3, E21): C19 showed that closing the range is what creates W2-1's first kills, but its
unconditional eastward press over-commits every scenario. A *selective* alternative: when a USV has no
assigned target but receives its own passive ESM bearing (被动告警, a legal observation), turn toward that
bearing to attempt active acquisition. Only warned units commit; unwarned units keep C10 behaviour.

Mechanism (ONE): after the base controller computes actions, for each alive, non-locking, target-less USV
that has a passive bearing attributed to it (`detected_by == unit`), replace its movement with a course
along that bearing. No scenario/route/strategy ID, no truth, no black-state read; lock/fire unchanged.
"""
import sys

from agent_hybrid_budget_gate import BudgetGateAgentMain, BudgetGateController
from agent_hybrid_v5 import USV_SPEED

POLICY_ID = "white-combat-0021-v1"
PARENT = "C10(white-combat-0010-v1)"
MECHANISM = "PASSIVE_BEARING_HOMING"


class PassiveHomeController(BudgetGateController):
    def step(self, obs, tracks, legal, alloc_result, events, intent=None, mission=None):
        actions = super().step(obs, tracks, legal, alloc_result, events, intent, mission)
        pm = {}
        for p in (getattr(obs, "passive", None) or []):
            db = p.get("detected_by")
            b = p.get("bearing")
            if db is not None and b is not None:
                pm.setdefault(db, b)
        pos = {u["name"]: (u["position"][0], u["position"][1]) for u in obs.usvs
               if u.get("is_alive") and u.get("position")}
        for name, (_x, _y) in pos.items():
            if self.targets.get(name):
                continue
            if self.state.get(name) == self.LOCKING:
                continue
            b = pm.get(name)
            if b is None:
                continue
            actions = [a for a in actions if a[0].split(" ", 1)[0] != name]
            actions.append((f"{name} 移动 target_speed={USV_SPEED:.1f} target_course={float(b) % 360:.1f}", "move"))
        return actions


class PassiveHomeAgentMain(BudgetGateAgentMain):
    def __init__(self, use_uavs=True, max_steps=40000):
        super().__init__(use_uavs=use_uavs, max_steps=max_steps)
        self.usv_ctrl = PassiveHomeController()


if __name__ == "__main__":
    use_uavs = True
    for a in sys.argv[1:]:
        if a == "--no-uav":
            use_uavs = False
    PassiveHomeAgentMain(use_uavs=use_uavs).run()
