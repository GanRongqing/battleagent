#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""agent_hybrid_safe_uav_search.py — C13: THREAT_AWARE_UAV_SEARCH.

Parent: ACE (agent_hybrid_allocator_expand.py). Candidate: white-combat-0013-v1.

Problem (E11 diagnosis): in W2-5 (and W2-1) all ten unarmed UAVs were destroyed within a single step at
12-30 km from Black — `UAVManager._global_search_fly` sent them to the highest-priority *unobserved* cell
without considering where known Black actually are, i.e. straight into the enemy engagement envelope.

Mechanism (ONE, minimal): when selecting a global-search cell, prefer unobserved cells that are at least
`SAFE_STANDOFF` (50 km, inside the UAV's 60 km radar) from any KNOWN positioned enemy track; if every
candidate is closer, pick the candidate farthest from the known threats. Uses only legal TrackManager
tracks (no truth, no route/strategy ID). All other UAV behaviour is unchanged.
"""
import math
import sys

from agent_hybrid_allocator_expand import ExpandAgentMain
from agent_hybrid_v5 import UAVManager

POLICY_ID = "white-combat-0013-v1"
PARENT = "ACE(white-combat-0002-v1)"
MECHANISM = "THREAT_AWARE_UAV_SEARCH"
SAFE_STANDOFF = 50_000.0


class ThreatAwareUAVManager(UAVManager):
    def step(self, obs, tracker, legal, events, intent=None, threat_fn=None, coverage=None, mission=None):
        # cache known positioned enemy positions (legal track state) for this step
        self._threat_pos = []
        try:
            for t in tracker.tracks.values():
                if not getattr(t, "has_position", False):
                    continue
                p = t.predicted_position(obs.now)
                if p is not None:
                    self._threat_pos.append((p[0], p[1]))
        except Exception:
            self._threat_pos = []
        return super().step(obs, tracker, legal, events, intent, threat_fn, coverage, mission)

    def _mind(self, c):
        if not getattr(self, "_threat_pos", None):
            return 1e18
        return min(math.hypot(c[0] - tx, c[1] - ty) for tx, ty in self._threat_pos)

    def _global_search_fly(self, name, pos, coverage, now, n_airborne):
        if coverage is None or pos is None or not getattr(self, "_threat_pos", None):
            return super()._global_search_fly(name, pos, coverage, now, n_airborne)
        targets = coverage.best_unobserved(now, k=max(1, n_airborne))
        if not targets:
            return self._search_fly(name, pos, n_airborne)
        centers = [c for c, _ in targets]
        safe = [c for c in centers if self._mind(c) >= SAFE_STANDOFF]
        center = safe[0] if safe else max(centers, key=self._mind)
        return self._fly(name, pos, center)


class SafeUAVAgentMain(ExpandAgentMain):
    def __init__(self, use_uavs=True, max_steps=40000):
        super().__init__(use_uavs=use_uavs, max_steps=max_steps)
        self.uav_mgr = ThreatAwareUAVManager(enabled=use_uavs)


if __name__ == "__main__":
    use_uavs = True
    for a in sys.argv[1:]:
        if a == "--no-uav":
            use_uavs = False
    SafeUAVAgentMain(use_uavs=use_uavs).run()
