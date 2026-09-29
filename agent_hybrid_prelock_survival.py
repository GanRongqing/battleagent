#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""white-combat-0004-v1 — SURVIVAL_AWARE_PRELOCK_ADMISSION (C3).

Parent: ACE (agent_hybrid_allocator_expand.py, white-combat-0002-v1).

Root cause (c3_root_cause_and_determinism, 0 new episodes): LA-F1 (assigned but never reached lock
range) decomposes to LA1-E WHITE_DIED_BEFORE_CLOSURE = 48.2% (6/6 strategies). Profile: the assigned
USV is committed to a FAR, HALF-LOST target (mean min-distance 102 km, visibility 0.53), closes without
ever entering lock range, and is killed while exposed. LA1-D (oscillation, 24.5%) and LA1-F (legal lock
missed, 13.9%) are secondary.

Mechanism (ONE): PRE-LOCK SURVIVAL ADMISSION. For a USV that is assigned but NOT yet locking, if it is
(a) EXPOSED (being locked by an enemy), AND (b) its target is LOST (not currently visible) or not
reachable soon, AND (c) it is FAR from friendly support, then DISENGAGE toward the nearest friendly USV
(rejoin support) instead of continuing the exposed, low-return approach.

This is ADMISSION control (do not commit into an exposed approach), not post-lock retreat.

Does NOT modify: allocator/ACE reserve logic, TrackManager, detection, radar, lock range, weapon, Black,
scenario, judge. Uses only legal observation + TrackManager belief + own state + legal actions.
"""
import math
import os
import sys

from agent_hybrid_v5 import (
    USVController, AgentMain, USV_SPEED, LOCK_RANGE, MISSION_NORMAL, bearing_to, _KILLED,
)

POLICY_ID = "white-combat-0004-v1"
PARENT = "ACE"
MECHANISM = "SURVIVAL_AWARE_PRELOCK_ADMISSION"
SUPPORT_RANGE = 50000.0


class PrelockSurvivalUSVController(USVController):
    def _nearest_friendly(self, pos, positions, exclude):
        best, bd = None, None
        for nm, p in positions.items():
            if nm == exclude or p is None:
                continue
            d = math.hypot(p[0] - pos[0], p[1] - pos[1])
            if bd is None or d < bd:
                best, bd = p, d
        return best, bd

    def step(self, obs, tracks, legal, alloc_result, events, intent=None, mission=MISSION_NORMAL):
        actions = super().step(obs, tracks, legal, alloc_result, events, intent, mission)
        positions = {u["name"]: (u["position"][0], u["position"][1])
                     for u in obs.usvs if u.get("is_alive") and u.get("position")}
        out = []
        for a in actions:
            nm = a[0].split()[0]
            if a[1] != "move" or nm not in positions:
                out.append(a)
                continue
            u = next((x for x in obs.usvs if x["name"] == nm), None)
            tgt = self.targets.get(nm)
            # only pre-lock (not currently locking)
            if u and u.get("is_locking"):
                out.append(a); continue
            if not tgt or tgt not in tracks:
                out.append(a); continue
            t = tracks[tgt]
            exposed = bool(u and (u.get("is_locked") or u.get("locked_attacker")))
            target_lost = not t.is_visible(obs.now)
            wp, sup = self._nearest_friendly(positions[nm], positions, nm)
            if exposed and target_lost and (sup is None or sup > SUPPORT_RANGE) and wp is not None:
                crs = bearing_to(positions[nm], wp)
                out.append((f"{nm} 移动 target_speed={USV_SPEED:.1f} target_course={crs:.1f}", "move"))
            else:
                out.append(a)
        return out


class PrelockSurvivalAgentMain(AgentMain):
    def __init__(self, use_uavs=True, max_steps=40000):
        super().__init__(use_uavs=use_uavs, max_steps=max_steps)
        from agent_hybrid_allocator_expand import ExpandingAllocator
        self.allocator = ExpandingAllocator()
        self.usv_ctrl = PrelockSurvivalUSVController()


if __name__ == "__main__":
    use_uavs = True
    for a in sys.argv[1:]:
        if a == "--no-uav":
            use_uavs = False
    PrelockSurvivalAgentMain(use_uavs=use_uavs).run()
