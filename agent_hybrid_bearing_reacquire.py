#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""agent_hybrid_bearing_reacquire.py — C12: BEARING_GUIDED_REACQUIRE.

Parent: ACE (agent_hybrid_allocator_expand.py). Candidate: white-combat-0012-v1.

Problem (E10 diagnosis): in W2-1 the Agent loses all UAVs early and the few radar contacts, then stays in
MISSION_GLOBAL_REACQUIRE holding a static screen at x=120 km. The inbound Black are subsequently known
only via passive bearings (absolute azimuth from the detecting unit), so no positioned track is formed and
White never locks/engages.

Mechanism (ONE, minimal): while in GLOBAL_REACQUIRE, an AVAILABLE USV that is currently receiving a passive
bearing alert steers along that **absolute bearing** (80 km ahead) instead of the static screen line, to
localise the emitter and create a positioned track. Uses only legal `obs.passive{name,bearing,detected_by}`
(engine azimuth) and own positions. No truth, no route/strategy ID, no lock/fire/weapon change.

When not in GLOBAL_REACQUIRE, or when no passive alert exists, behaviour is identical to ACE.
"""
import math
import sys

from agent_hybrid_allocator_expand import ExpandAgentMain
from agent_hybrid_v5 import USVController, MISSION_GLOBAL_REACQUIRE

POLICY_ID = "white-combat-0012-v1"
PARENT = "ACE(white-combat-0002-v1)"
MECHANISM = "BEARING_GUIDED_REACQUIRE"
AIM_DIST = 80_000.0


class BearingReacquireController(USVController):
    def step(self, obs, tracks, legal, alloc_result, events, intent=None, mission=None):
        actions = super().step(obs, tracks, legal, alloc_result, events, intent, mission)
        if mission != MISSION_GLOBAL_REACQUIRE:
            return actions
        passives = getattr(obs, "passive", None) or []
        if not passives:
            return actions
        pos = {u["name"]: (u["position"][0], u["position"][1]) for u in obs.usvs
               if u.get("is_alive") and u.get("position")}
        steered = set()
        for p in passives:
            db = p.get("detected_by")
            brg = p.get("bearing")
            if db in pos and brg is not None and db not in steered \
                    and self.state.get(db) == self.AVAILABLE:
                rad = math.radians(float(brg))
                x, y = pos[db]
                aim = (x + AIM_DIST * math.sin(rad), y + AIM_DIST * math.cos(rad))
                actions = [a for a in actions if a[0].split(" ", 1)[0] != db]
                actions.append(self._move(db, pos[db], aim))
                steered.add(db)
        return actions


class BearingReacquireAgentMain(ExpandAgentMain):
    def __init__(self, use_uavs=True, max_steps=40000):
        super().__init__(use_uavs=use_uavs, max_steps=max_steps)
        self.usv_ctrl = BearingReacquireController()


if __name__ == "__main__":
    use_uavs = True
    for a in sys.argv[1:]:
        if a == "--no-uav":
            use_uavs = False
    BearingReacquireAgentMain(use_uavs=use_uavs).run()
