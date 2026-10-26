#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""agent_hybrid_standoff_hold.py — C22: CONTACT_STANDOFF_HOLD.

Parent: C19 (agent_hybrid_press_search.py). Candidate: white-combat-0022-v1.

Evidence (E22 P0): in C19 all 20 White USVs are wiped between 02:58:30 and 03:13:30 by a *mass freeze*
(Black 冻结) then destruction, at close range (min USV→Black 17.4 km). Engaged units stand off at
LOCK_BAND, but target-less units keep pressing east into Black's freeze envelope, so the fleet enters
close range as a blob and is frozen en masse. The 4 kills occur inside that brawl (hence C20's first-loss
global retreat erases them).

Mechanism (ONE, per-unit): when active ship tracks exist, a USV with **no assigned target** holds a
standoff ring (`LOCK_BAND_OUTER` ≈ 36.5 km, still inside its own 40 km lock range) around the nearest
active contact instead of pressing east. Units with a target, locking, or when no contact exists keep
C19 behaviour. No scenario/route ID, no truth, no black-state read.
"""
import math
import sys

from agent_hybrid_press_search import PressSearchAgentMain, PressSearchController
from agent_hybrid_v5 import LOCK_BAND_OUTER, USV_SPEED

POLICY_ID = "white-combat-0022-v1"
PARENT = "C19(white-combat-0019-v1)"
MECHANISM = "CONTACT_STANDOFF_HOLD"
STANDOFF = LOCK_BAND_OUTER


class StandoffHoldController(PressSearchController):
    def step(self, obs, tracks, legal, alloc_result, events, intent=None, mission=None):
        actions = super().step(obs, tracks, legal, alloc_result, events, intent, mission)
        contacts = []
        for t in tracks.values():
            if getattr(t, "is_ship", False) and getattr(t, "has_position", False) and t.is_visible(obs.now):
                tp = t.predicted_position(obs.now)
                if tp is not None:
                    contacts.append(tp)
        if not contacts:
            return actions
        pos = {u["name"]: (u["position"][0], u["position"][1]) for u in obs.usvs
               if u.get("is_alive") and u.get("position")}
        for name, (x, y) in pos.items():
            if self.targets.get(name):
                continue
            if self.state.get(name) == self.LOCKING:
                continue
            bx, by = min(contacts, key=lambda c: math.hypot(c[0] - x, c[1] - y))
            d = math.hypot(bx - x, by - y)
            if d < 1.0:
                wp = (x, y)
            else:
                s = STANDOFF / d
                wp = (bx + (x - bx) * s, by + (y - by) * s)
            actions = [a for a in actions if a[0].split(" ", 1)[0] != name]
            actions.append(self._move(name, (x, y), wp))
        return actions


class StandoffHoldAgentMain(PressSearchAgentMain):
    def __init__(self, use_uavs=True, max_steps=40000):
        super().__init__(use_uavs=use_uavs, max_steps=max_steps)
        self.usv_ctrl = StandoffHoldController()


if __name__ == "__main__":
    use_uavs = True
    for a in sys.argv[1:]:
        if a == "--no-uav":
            use_uavs = False
    StandoffHoldAgentMain(use_uavs=use_uavs).run()
