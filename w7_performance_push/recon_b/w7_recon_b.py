# -*- coding: utf-8 -*-
"""w7_performance_push/recon_b/w7_recon_b.py — coverage-gap dynamic screen (recon-b1).

Hypothesis under test: B3 rewards a fleet that stays globally balanced (no empty lanes /
empty capacity), not one that piles sensing on the current most visible target. recon-b1 adds
a REGION-priority UAV task that fills low-coverage, threat-relevant lanes instead of stacking
on the top target.

Design (legal, scale-agnostic, no hidden truth):
  - coverage axis bins are derived from the map x-span and the legal track lanes actually seen
    (historical first-seen per y-bin memory, not enemy count assumptions).
  - coverage_need(bin) = threat_presence(bin) * (1 - recent_coverage(bin))
  - a SEARCH UAV is re-targeted to the bin with max coverage_need when it is not needed for an
    imminent lost/reacquire or critical maintenance duty (base handles those first).
USV allocator/controller/HOW = W5 (unchanged).
"""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from agent_hybrid_v5 import AgentMain, UAVManager  # noqa: E402

BINS = 8                     # lateral axis bins (scale-agnostic resolution)
GAP_MIN_RECENT = 0.0         # fully uncovered bin
GAP_FRACTION = 0.35          # how far into the uncovered bin to place the probe


def _bins_of_span(y_min, y_max):
    return [y_min + i * (y_max - y_min) / BINS for i in range(BINS + 1)]


def coverage_need_by_bin(recent_covered, threat_presence, y_min, y_max):
    """recent_covered/ threat_presence: dict bin_index -> [0,1]. Returns list of (bin, need)."""
    need = []
    for i in range(BINS):
        cov = recent_covered.get(i, 0.0)
        thr = threat_presence.get(i, 0.0)
        # region priority: only holes in threat-relevant lanes matter
        if thr <= 0.0:
            need.append((i, 0.0))
            continue
        need.append((i, thr * max(0.0, 1.0 - cov)))
    return need


def best_gap_bin(recent_covered, threat_presence, y_min, y_max, exclude=None):
    """Highest threat-relevant uncovered bin (excludes already-covered / no-threat)."""
    need = coverage_need_by_bin(recent_covered, threat_presence, y_min, y_max)
    if exclude:
        need = [x for x in need if x[0] not in exclude]
    best = max(need, key=lambda x: x[1])
    return best if best[1] > 1e-6 else None


class CoverageGapUAVManager(UAVManager):
    """W5 UAVManager + recon-b1 coverage-gap search bias (UAV task only)."""

    def __init__(self, enabled=True):
        super().__init__(enabled=enabled)
        self.gap_assignments = 0
        self._bins = BINS

    def step(self, obs, tracker, legal, events, intent=None, threat_fn=None,
             coverage=None, mission=None):
        from agent_hybrid_v5 import MISSION_NORMAL as _MN
        actions = super().step(obs, tracker, legal, events, intent=intent,
                               threat_fn=threat_fn, coverage=coverage,
                               mission=_MN if mission is None else mission)
        # recon-b1 post-pass: redirect ONE airborne SEARCH UAV toward the top coverage gap.
        try:
            now = obs.now
            gap = self._gap_target(obs, tracker, now)
            if gap is None:
                return actions
            # choose a UAV currently in SEARCH whose base action is a fly
            search_uavs = [u["name"] for u in obs.uavs
                           if u.get("is_alive") and self.state.get(u["name"]) == self.SEARCH
                           and u.get("position")]
            if not search_uavs:
                return actions
            target = search_uavs[0]
            up = next((u for u in obs.uavs if u["name"] == target), None)
            pos = up.get("position") if up else None
            if not pos:
                return actions
            from agent_hybrid_v5 import bearing_to, UAV_FLY_SPEED
            crs = bearing_to((pos[0], pos[1]), gap)
            for i, act in enumerate(actions):
                if isinstance(act, tuple) and len(act) == 2 and act[1] == "fly" and \
                        act[0].startswith(target + " 飞行"):
                    actions[i] = (f"{target} 飞行 target_speed={UAV_FLY_SPEED:.1f} "
                                  f"target_course={crs:.1f}", "fly")
                    self.gap_assignments += 1
                    break
        except Exception:
            pass
        return actions

    def _gap_target(self, obs, tracker, now):
        """Return (x, y) for the highest coverage_need lane bin, or None."""
        alive = [u for u in obs.uavs if u.get("is_alive") and u.get("position")]
        if not alive:
            return None
        ys = [u["position"][1] for u in alive if u.get("position")]
        if not ys:
            return None
        y_min, y_max = min(ys), max(ys)
        span_edges = _bins_of_span(y_min, y_max)
        # threat_presence: fraction of ship-track lanes seen per bin (legal memory over run)
        # (approximated per step from current visible ship tracks + sticky lane memory)
        bins = [0.0] * BINS
        lane_mem = getattr(self, "_threat_lanes", {})
        for name, t in tracker.tracks.items():
            if not t.is_ship or not t.has_position:
                continue
            lane_mem[name] = t.predicted_position(now)[1] if t.predicted_position(now) else \
                (t.last_position[1] if t.last_position else None)
        self._threat_lanes = lane_mem
        for y in lane_mem.values():
            if y is None:
                continue
            for i in range(BINS):
                if span_edges[i] <= y < span_edges[i + 1] + 1e-6:
                    bins[i] = 1.0
                    break
        threat = {i: 1.0 if bins[i] > 0 else 0.0 for i in range(BINS)}
        # recent_covered: coarse — UAV/USV proximity to the bin center in the last step set to 1
        recent = {i: 0.0 for i in range(BINS)}
        centers = [(span_edges[i] + span_edges[i + 1]) / 2 for i in range(BINS)]
        for u in obs.usvs + obs.uavs:
            p = u.get("position") if u.get("is_alive") else None
            if not p:
                continue
            for i, cy in enumerate(centers):
                if abs(p[1] - cy) <= (span_edges[1] - span_edges[0]):
                    recent[i] = 1.0
        g = best_gap_bin(recent, threat, y_min, y_max)
        if g is None:
            return None
        self.gap_assignments += 1
        cy = centers[g[0]]
        # probe placed at SCREEN_X-ish front (legal forward anchor) inside the gap bin
        from agent_hybrid_v5 import SCREEN_X
        return (float(SCREEN_X), float(cy))


class W7ReconB1Agent(AgentMain):
    """W5 + recon-b1 coverage-gap UAV search bias. USV = W5 exactly."""
    def __init__(self, use_uavs=True, max_steps=40000):
        super().__init__(use_uavs=use_uavs, max_steps=max_steps)
        self.uav_mgr = CoverageGapUAVManager(enabled=use_uavs)
