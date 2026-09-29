#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""white-combat-0002-v1 — ALLOCATOR_COMMITMENT_EXPANSION (breadth-first).

Parent: Frozen W5 (agent_hybrid_v5.py).

Primary hypothesis (from f1_root_cause_audit): W5 under-commits — it leaves FREE combat USVs
idle while VISIBLE, actionable, zero-owner hostile targets exist. Root cause: the frozen default
StrategicIntent (LLM off) reserves 20% of free USVs (reserve_ratio=0.20) and commits only a subset.

Mechanism (ONE mechanism): BREADTH-FIRST COMMITMENT EXPANSION with DYNAMIC RESERVE RELEASE.
  - When under-commitment is detected (a visible actionable ship has zero owners AND a free combat
    USV exists), release the static reserve (reserve_usvs -> 0) so the allocator's existing
    "coverage floor" pass can assign the free USV to the 0-owner target.
  - The allocator's own PASS1 (zero-owner coverage) / PASS2 (marginal concentration) order is kept
    (W5 already does 0->1 before 2->3). We do NOT add a new 3rd-attacker policy.
  - When no under-commitment exists, the reserve semantics are preserved unchanged.

Does NOT modify: TrackManager, Detection, UAV radar, CoverageMap, sensor/lock/weapon ranges, speed,
Black route/speed, scenario, simulator, judge, terminal condition.
Does NOT read hidden truth / future waypoints / strategy name / fixed counts.

Fair-play: uses only legal observation + TrackManager belief (t.is_visible, t.is_ship, t.assigned_usvs).
"""
import os
import sys

from agent_hybrid_v5 import (
    ThreatAllocator, StrategicIntent, AgentMain, _KILLED,
)

POLICY_ID = "white-combat-0002-v1"
PARENT = "W5"
MECHANISM = "ALLOCATOR_COMMITMENT_EXPANSION"


class ExpandingAllocator(ThreatAllocator):
    """ThreatAllocator + dynamic reserve release under under-commitment."""

    def _under_commitment(self, tracks, usvs, usv_map, now):
        # free combat USV exists (usv_map owner is None, alive, has position)
        alive_pos = {u["name"] for u in usvs if u.get("is_alive") and u.get("position")}
        if not any(trg is None and name in alive_pos for name, trg in usv_map.items()):
            return False
        # visible actionable ship with zero owners
        for name, t in tracks.items():
            if name in _KILLED or not t.is_ship or not t.has_position:
                continue
            if not t.is_visible(now):
                continue
            if len(t.assigned_usvs) > 0:
                continue
            return True
        return False

    def _released(self, intent):
        return StrategicIntent(
            posture=intent.posture,
            focus_level=intent.focus_level,
            emergency_focus_level=intent.emergency_focus_level,
            reserve_usvs=0,                      # release static reserve
            reserve_ratio=intent.reserve_ratio,
            threat_bias=intent.threat_bias,
            priority_tracks=intent.priority_tracks,
            uav_mode=intent.uav_mode,
            uav_priority_tracks=intent.uav_priority_tracks,
            recon_aggressiveness=intent.recon_aggressiveness,
            engagement_aggressiveness=intent.engagement_aggressiveness,
            overmatch_policy=intent.overmatch_policy,
            recon_mode=intent.recon_mode,
            standoff_preference=intent.standoff_preference,
            uncertainty_tolerance=intent.uncertainty_tolerance,
            coverage_priority=intent.coverage_priority,
            priority_clusters=intent.priority_clusters,
            reason=intent.reason,
        )

    def allocate_usvs(self, tracks, usvs, usv_map, now, intent=None,
                      return_margin=False, candidates=None):
        if intent is not None and self._under_commitment(tracks, usvs, usv_map, now):
            intent = self._released(intent)
        return super().allocate_usvs(tracks, usvs, usv_map, now, intent,
                                     return_margin, candidates)


class ExpandAgentMain(AgentMain):
    def __init__(self, use_uavs=True, max_steps=40000):
        super().__init__(use_uavs=use_uavs, max_steps=max_steps)
        self.allocator = ExpandingAllocator()


if __name__ == "__main__":
    use_uavs = True
    for a in sys.argv[1:]:
        if a == "--no-uav":
            use_uavs = False
    ExpandAgentMain(use_uavs=use_uavs).run()
