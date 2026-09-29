#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""white-combat-0005-v1 — REACHABILITY_WEIGHTED_COMMITMENT.

Parent: ACE (agent_hybrid_allocator_expand.py / white-combat-0002-v1).

Primary hypothesis (from c3 la_f1_audit): the dominant residual no-lock cause is
LA1-E WHITE_DIED_BEFORE_CLOSURE (48.2%, 6/6 strategies): a committed USV dies while still
transiting toward its target (profile: far target, min ~102 km, and half-lost vis~0.53).
W5/ACE score targets by proximity-to-breakthrough + confidence but do NOT consider the
travel cost from the free USVs; so several USVs are sent on long exposed transits that end
in death before any lock.

Mechanism (ONE mechanism): REACHABILITY DECAY on the CONCENTRATION pass only.
  - Pass 1 (coverage floor) is UNCHANGED: every actionable ship still gets >= 1 attacker,
    so no ship is left free to break through.
  - Pass 2 (marginal concentration, i.e. adding a 2nd/3rd attacker) multiplies the target
    value by a reachability factor reach = clamp(REACH_FLOOR, 1 - d_near / REACH_SCALE, 1),
    where d_near = distance from the NEAREST FREE combat USV to the target. Far targets
    attract fewer overmatch attackers; near targets keep their concentration.
  - Emergency (target inside the urgent breakthrough line) is exempt: reach = 1.

Does NOT modify: TrackManager, Detection, UAV radar, CoverageMap, sensor/lock/weapon ranges,
speed, Black route/speed, scenario, simulator, judge, terminal condition.
Does NOT read hidden truth / future waypoints / strategy name / fixed counts.
Fair-play: legal observation + TrackManager belief only.
"""
import math
import sys

from agent_hybrid_allocator_expand import ExpandingAllocator, ExpandAgentMain, _KILLED
from agent_hybrid_v5 import (
    StrategicIntent,  # noqa: F401  (re-export convenience)
    EMERGENCY_3V1_X,
)

POLICY_ID = "white-combat-0005-v1"
PARENT = "ACE(white-combat-0002-v1)"
MECHANISM = "REACHABILITY_WEIGHTED_COMMITMENT"


class ReachabilityAllocator(ExpandingAllocator):
    """ACE allocator + reachability decay on the concentration pass."""

    REACH_SCALE = 250_000.0   # m; distance at which reach decays to REACH_FLOOR
    REACH_FLOOR = 0.25        # minimum reach factor (never fully zero out a target)

    def _nearest_free_dist(self, t, now, usvs, usv_map):
        pos = t.predicted_position(now)
        if pos is None:
            return None
        free = {n for n, trg in usv_map.items() if trg is None}
        best = float("inf")
        for u in usvs:
            if not u.get("is_alive") or not u.get("position"):
                continue
            if u["name"] not in free:
                continue
            up = u["position"]
            d = math.hypot(up[0] - pos[0], up[1] - pos[1])
            if d < best:
                best = d
        return None if best == float("inf") else best

    def _reach_factor(self, t, now, usvs, usv_map):
        pos = t.predicted_position(now)
        if pos is not None and pos[0] < self.URGENT_X:
            return 1.0  # emergency: exempt
        d = self._nearest_free_dist(t, now, usvs, usv_map)
        if d is None:
            return 1.0
        return max(self.REACH_FLOOR, min(1.0, 1.0 - d / self.REACH_SCALE))

    def allocate_usvs(self, tracks, usvs, usv_map, now, intent=None,
                      return_margin=False, candidates=None):
        # ACE mechanism first (dynamic reserve release under under-commitment).
        if intent is not None and self._under_commitment(tracks, usvs, usv_map, now):
            intent = self._released(intent)

        # Only Pass 2 is reachability-weighted. Pass 1 must be untouched, so we cannot simply
        # scale threat_score. Instead: run the parent, then if the parent (after Pass 1) is
        # about to add a 2nd attacker to a far target, we can't intercept it -> so we instead
        # run the parent on the full set, then DEMOTE far-target overmatch by re-running Pass 2
        # ourselves against the parent's Pass-1 result is not exposed. Simplest faithful
        # approach: re-implement the concentration ordering using the parent's helper policy by
        # temporarily boosting near targets' threat via a value pre-multiplier is not possible
        # either. => We call the parent but pre-sort is internal. To keep ONE mechanism and be
        # faithful, replicate the parent loop with the single reach multiplier on target_value.
        return self._allocate_with_reach(tracks, usvs, usv_map, now, intent,
                                         return_margin, candidates)

    def _allocate_with_reach(self, tracks, usvs, usv_map, now, intent,
                             return_margin, candidates):
        # Faithful copy of W5 allocate_usvs with exactly one change: reach multiplier on the
        # Pass-2 target value. Kept in sync with agent_hybrid_v5.py:1798.
        usv_pos = {u["name"]: (u["position"][0], u["position"][1])
                   for u in usvs if u.get("is_alive") and u.get("position")}
        available = [name for name, trg in usv_map.items()
                     if trg is None and name in usv_pos]
        if not available:
            return ({}, None) if return_margin else {}

        focus = intent.focus_level if intent else 2
        emg = intent.emergency_focus_level if intent else 3
        agg = intent.engagement_aggressiveness if intent else 0.5
        emg_x = EMERGENCY_3V1_X * (0.5 + agg)

        om = getattr(intent, "overmatch_policy", "balanced") if intent else "balanced"
        om_scale = {"economical": 1.6, "balanced": 1.0, "decisive": 0.6}.get(om, 1.0)
        min_assign = self.MIN_ASSIGN_VALUE * om_scale
        unc_tol = getattr(intent, "uncertainty_tolerance", 0.35) if intent else 0.35
        guard_threshold = max(0.15, min(0.60, 0.55 - unc_tol))

        ships = []
        for name, t in tracks.items():
            if not t.is_ship or not t.has_position or name in _KILLED:
                continue
            ships.append((name, t))

        def commit_guard(t):
            if t.is_visible(now):
                return False
            if t.point_confidence < guard_threshold:
                pos = t.predicted_position(now)
                if pos is not None and pos[0] < self.URGENT_X:
                    return False
                return True
            return False

        def _any_urgent():
            for _, t in ships:
                if not commit_guard(t):
                    pos = t.predicted_position(now)
                    if pos is not None and pos[0] < emg_x:
                        return True
            return False

        emergency = _any_urgent()
        reserve = 0
        if intent and not emergency:
            if intent.reserve_usvs is not None:
                reserve = max(0, min(intent.reserve_usvs, len(available)))
            else:
                ratio = getattr(intent, "reserve_ratio", 0.20)
                reserve = int(round(len(available) * ratio))
                reserve = max(0, min(reserve, len(available)))
        if reserve and len(available) <= reserve:
            return ({}, None) if return_margin else {}
        if reserve:
            available = available[:-reserve]

        def target_value(name, t):
            cur = len(t.assigned_usvs)
            if cur >= emg:
                return 0.0
            base = self.threat_score(t, now, intent=intent, usvs=usvs)
            if intent and name in intent.priority_tracks:
                base += 0.3
            mg = self.marginal_gain(cur)
            if not t.is_visible(now) and t.point_confidence < guard_threshold:
                pos = t.predicted_position(now)
                if pos is not None and pos[0] >= self.URGENT_X:
                    mg *= 0.35
            return base * mg

        def _assign_one(target_name, target_pos):
            nonlocal available
            best_usv, bestd = None, float("inf")
            for uname in available:
                ux, uy = usv_pos[uname]
                d = math.hypot(ux - target_pos[0], uy - target_pos[1]) if target_pos else 0.0
                if d < bestd:
                    bestd, best_usv = d, uname
            if best_usv is None:
                return False
            available.remove(best_usv)
            result.setdefault(target_name, []).append(best_usv)
            tracks[target_name].assigned_usvs.add(best_usv)
            if not tracks[target_name].is_visible(now) and \
                    tracks[target_name].point_confidence < guard_threshold:
                self.low_conf_commitments += 1
            return True

        result = {}
        # Pass 1: coverage floor (UNCHANGED).
        for name, t in sorted(ships, key=lambda x: -self.threat_score(x[1], now, intent=intent)):
            if not available:
                break
            if len(t.assigned_usvs) > 0:
                continue
            if commit_guard(t):
                continue
            tpos = t.predicted_position(now)
            if tpos is None:
                continue
            _assign_one(name, tpos)

        # Pass 2: marginal concentration WITH reachability decay (THE mechanism).
        margin = None
        while available:
            best_name, best_val = None, 0.0
            second_val = 0.0
            guarded = []
            for name, t in ships:
                if commit_guard(t):
                    guarded.append((name, t))
                    continue
                cur = len(t.assigned_usvs)
                if cur >= emg:
                    continue
                v = target_value(name, t) * self._reach_factor(t, now, usvs, usv_map)
                if v > best_val:
                    second_val = best_val
                    best_val, best_name = v, name
                elif v > second_val:
                    second_val = v
            if best_name is None:
                active_engagement = any(len(t.assigned_usvs) > 0 for _, t in ships)
                if not active_engagement and guarded:
                    name, t = max(guarded, key=lambda x: self.threat_score(x[1], now, intent=intent))
                    if self.threat_score(t, now, intent=intent) * self.marginal_gain(len(t.assigned_usvs)) >= min_assign:
                        best_name, best_val = name, 0.0
            if best_name is None or best_val < min_assign:
                break
            margin = best_val - second_val if best_val > 0 else 0.0
            if candidates is not None:
                candidates.append({
                    "target": best_name, "value": round(best_val, 4),
                    "second_value": round(second_val, 4),
                    "margin": round(margin, 5),
                    "assigned_after": len(tracks[best_name].assigned_usvs) + 1})
            t = tracks[best_name]
            tpos = t.predicted_position(now)
            if tpos is None or not _assign_one(best_name, tpos):
                break

        return (result, margin) if return_margin else result


class ReachCommitAgentMain(ExpandAgentMain):
    def __init__(self, use_uavs=True, max_steps=40000):
        super().__init__(use_uavs=use_uavs, max_steps=max_steps)
        self.allocator = ReachabilityAllocator()


if __name__ == "__main__":
    use_uavs = True
    for a in sys.argv[1:]:
        if a == "--no-uav":
            use_uavs = False
    ReachCommitAgentMain(use_uavs=use_uavs).run()
