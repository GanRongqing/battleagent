#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""agent_hybrid_prelock_admission.py — C6B: PRE_LOCK_ENGAGEMENT_ADMISSION (exposure governor).

Parent: ACE (agent_hybrid_allocator_expand.py). Candidate: white-combat-0007-v1.

Mechanism (ONE): a bounded PRE-LOCK admission gate using ONLY observable own/support geometry.
- ENGAGED (own active lock) -> exact ACE behaviour.
- SAFE_TO_COMMIT (supported / not overextended / no target) -> exact ACE behaviour (no-op).
- SHAPE_AND_WAIT (pre-lock, forward-overextended beyond local friendly support) -> replace the
  aggressive forward move with a lateral shaping move so support can close; bounded by MAX_SHAPE_WAIT.

UNCHANGED: TrackManager, ThreatAllocator/ACE, reserve, coverage, lock legality, fire legality,
sensor semantics, Black strategies, simulator.
NO truth, NO route/strategy-ID logic, NO retreat-after-lock, NO focus fire, NO search change.
"""
import math
import sys

from agent_hybrid_allocator_expand import ExpandAgentMain
from agent_hybrid_v5 import USVController, USV_SPEED, bearing_to, _KILLED

POLICY_ID = "white-combat-0007-v1"
PARENT = "ACE(white-combat-0002-v1)"
MECHANISM = "PRE_LOCK_ENGAGEMENT_ADMISSION"

SUPPORT_RADIUS = 40_000.0     # m; local friendly support search radius
MIN_SUPPORT = 3               # need >= this many friendly combat USVs nearby to commit forward
OVEREXT_ENTER = 45_000.0      # m; lead over local friendly centroid to trigger SHAPE_AND_WAIT
OVEREXT_EXIT = 25_000.0       # m; hysteresis exit
MIN_HOLD_STEPS = 4            # min macro-steps in SHAPE_AND_WAIT before release
MAX_SHAPE_WAIT = 20           # macro-steps; then allow progression again


class AdmissionController(USVController):
    def __init__(self):
        super().__init__()
        self._wait = {}      # usv_name -> consecutive SHAPE_AND_WAIT step count
        self.admission_events = []   # diagnostics only

    def _local_support(self, name, pos, obs):
        """(nearest_support_dist, support_count, local_centroid_x)."""
        best = float("inf"); cnt = 0; xs = []
        for u in obs.usvs:
            if not u.get("is_alive") or u["name"] == name or not u.get("position"):
                continue
            d = math.hypot(u["position"][0] - pos[0], u["position"][1] - pos[1])
            if d <= SUPPORT_RADIUS:
                cnt += 1; xs.append(u["position"][0])
                if d < best:
                    best = d
        cen = (sum(xs) / len(xs)) if xs else pos[0]
        return best, cnt, cen

    def _admission(self, name, pos, obs, target):
        """Return 'SHAPE_AND_WAIT' or None (SAFE/ENGAGED)."""
        if pos is None or not target:
            return None
        near, cnt, cen = self._local_support(name, pos, obs)
        overext = pos[0] - cen          # westward lead over local friendly centroid
        prev = self._wait.get(name, 0)
        if prev > 0:
            # already waiting: stay until support/overextension healed, min hold, max wait
            if prev >= MAX_SHAPE_WAIT:
                return None
            if overext < OVEREXT_EXIT and cnt >= MIN_SUPPORT and prev >= MIN_HOLD_STEPS:
                return None
            return "SHAPE_AND_WAIT"
        # isolated (few nearby friendlies) OR forward-overextended -> do not commit aggressively
        if cnt < MIN_SUPPORT or overext > OVEREXT_ENTER:
            return "SHAPE_AND_WAIT"
        return None

    def step(self, obs, tracks, legal, alloc_result, events, intent=None, mission=None):
        actions = super().step(obs, tracks, legal, alloc_result, events, intent, mission)
        for u in obs.usvs:
            if not u.get("is_alive") or not u.get("position"):
                continue
            name = u["name"]
            st = self.state.get(name)
            # ENGAGED (own active lock) or already frozen/dead -> no interference
            if st == self.LOCKING:
                self._wait.pop(name, None)
                continue
            tname = self.targets.get(name)
            t = tracks.get(tname) if tname else None
            # gate applies only pre-lock AND while assigned to a real, non-killed target
            if not tname or t is None or tname in _KILLED:
                self._wait.pop(name, None)
                continue
            pos = (u["position"][0], u["position"][1])
            decision = self._admission(name, pos, obs, tname)
            if decision == "SHAPE_AND_WAIT":
                self._wait[name] = self._wait.get(name, 0) + 1
                self.admission_events.append(("SHAPE_AND_WAIT", name, round(self._wait[name], 1)))
                # lateral shaping: offset perpendicular to the (own->target) bearing, slow advance
                if t.has_position:
                    tpos = t.predicted_position(obs.now)
                    if tpos is not None:
                        brg = bearing_to(pos, tpos)
                        crs = (brg + 35.0) % 360.0
                        act = (f"{name} 移动 target_speed={USV_SPEED * 0.6:.1f} target_course={crs:.1f}", "move")
                        actions = [a for a in actions if not (a[0].split(" ", 1)[0] == name and a[1] == "move")]
                        actions.append(act)
            else:
                self._wait.pop(name, None)
        return actions


class PrelockAdmissionAgentMain(ExpandAgentMain):
    def __init__(self, use_uavs=True, max_steps=40000):
        super().__init__(use_uavs=use_uavs, max_steps=max_steps)
        self.usv_ctrl = AdmissionController()


if __name__ == "__main__":
    use_uavs = True
    for a in sys.argv[1:]:
        if a == "--no-uav":
            use_uavs = False
    PrelockAdmissionAgentMain(use_uavs=use_uavs).run()
