#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""white-combat-0003-v1 — LOCK-FIRST APPROACH (C2).

Parent: ACE (agent_hybrid_allocator_expand.py, white-combat-0002-v1).

Root cause (lock_acquisition_c2, 0 new episodes): per-assignment lock rate is 71.6%, but the no-lock
failures are dominated by LA-F1 NEVER_CLOSED_TO_LOCK_RANGE (70.7%, all 6 strategies). W5's USVController
already moves toward the target when dist >= LOCK_RANGE, so the closure failure happens for stale/lost
targets: `if not t.is_visible(): standoff(34km)` — the USV converges to its own radar instead of
continuing to close, and the assignment ends without ever reaching LOCK_RANGE.

Mechanism (ONE): before the FIRST lock of the current target, prioritise entering the lock envelope
(close toward the tracked/predicted position) instead of holding the standoff band. After the first lock
(POST_LOCK), the original W5/ACE standoff behaviour is fully restored.

Does NOT modify: allocator/ACE reserve logic, TrackManager, detection, radar, lock range, weapon,
Black, scenario, judge. Uses only legal observation + TrackManager belief + own USV state + legal actions.
"""
import os
import sys

from agent_hybrid_v5 import (
    USVController, AgentMain, USV_SPEED, LOCK_RANGE, MISSION_NORMAL, bearing_to,
)

POLICY_ID = "white-combat-0003-v1"
PARENT = "ACE"
MECHANISM = "LOCK_FIRST_APPROACH"


class LockFirstUSVController(USVController):
    """USVController + LOCK-FIRST APPROACH (pre-lock closure, post-lock unchanged)."""

    def __init__(self):
        super().__init__()
        self._locked = {}   # usv_name -> set(target names it has ever locked)

    def step(self, obs, tracks, legal, alloc_result, events, intent=None, mission=MISSION_NORMAL):
        actions = super().step(obs, tracks, legal, alloc_result, events, intent, mission)
        # record locks observed this step
        for u in obs.usvs:
            if u.get("is_locking") and u.get("locking_unit"):
                self._locked.setdefault(u["name"], set()).add(u["locking_unit"])
        pos = {u["name"]: (u["position"][0], u["position"][1])
               for u in obs.usvs if u.get("is_alive") and u.get("position")}

        out = []
        for a in actions:
            nm = a[0].split()[0]
            # only touch ordinary moves for pre-lock intercepting USVs; never override a lock action
            if a[1] != "move" or nm not in pos:
                out.append(a)
                continue
            tgt = self.targets.get(nm)
            if not tgt or tgt not in tracks or tgt in self._locked.get(nm, set()):
                out.append(a)          # post-lock or no target -> original behaviour
                continue
            t = tracks[tgt]
            if not t.has_position:
                out.append(a)
                continue
            tpos = t.predicted_position(obs.now)
            if tpos is None:
                out.append(a)
                continue
            # PRE-LOCK: always close toward the target (ignore standoff band)
            crs = bearing_to(pos[nm], tpos)
            out.append((f"{nm} 移动 target_speed={USV_SPEED:.1f} target_course={crs:.1f}", "move"))
        return out


class LockFirstAgentMain(AgentMain):
    def __init__(self, use_uavs=True, max_steps=40000):
        super().__init__(use_uavs=use_uavs, max_steps=max_steps)
        # keep ACE's allocator
        from agent_hybrid_allocator_expand import ExpandingAllocator
        self.allocator = ExpandingAllocator()
        self.usv_ctrl = LockFirstUSVController()


if __name__ == "__main__":
    use_uavs = True
    for a in sys.argv[1:]:
        if a == "--no-uav":
            use_uavs = False
    LockFirstAgentMain(use_uavs=use_uavs).run()
