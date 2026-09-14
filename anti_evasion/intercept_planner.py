# -*- coding: utf-8 -*-
"""anti_evasion/intercept_planner.py — InterceptPlanner.

W6 Module 1 (part 2): computes a feasible INTERCEPT POINT along a target's predicted
corridor, instead of chasing the target's current position.

Outputs: intercept_point, intercept_eta, target_eta, intercept_feasible, intercept_margin.

The target is treated as a CORRIDOR (center + uncertainty); the interceptor aims at a
point along the corridor ahead of the target, keeping at least `standoff` from the
corridor center (so it does not knife-fight into the target). ETA is time-of-flight at
the interceptor's speed; margin = target_eta - intercept_eta (normalized).
"""
import math

from . import config as cfg


class InterceptPlan:
    __slots__ = ("track_name", "interceptor", "intercept_point", "intercept_eta",
                 "target_eta", "intercept_feasible", "intercept_margin",
                 "geometry_state")

    def __init__(self, track_name, interceptor, point, ieta, teta, feasible, margin,
                 geometry_state="INTERCEPT_APPROACH"):
        self.track_name = track_name
        self.interceptor = interceptor
        self.intercept_point = point
        self.intercept_eta = ieta
        self.target_eta = teta
        self.intercept_feasible = feasible
        self.intercept_margin = margin
        self.geometry_state = geometry_state

    def to_dict(self):
        return {"track_name": self.track_name, "interceptor": self.interceptor,
                "intercept_point": list(self.intercept_point),
                "intercept_eta": round(self.intercept_eta, 1),
                "target_eta": round(self.target_eta, 1),
                "intercept_feasible": self.intercept_feasible,
                "intercept_margin": round(self.intercept_margin, 4),
                "geometry_state": self.geometry_state}


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


class InterceptPlanner:
    """Standoff-aware predictive interception.

    The raw intercept point is the corridor point the interceptor can reach earliest.
    It is then projected to the legacy standoff band around the TARGET:
      - if the raw intercept point would put the interceptor INSIDE the target band,
        project it outward (REPOSITION_OUTWARD) to the standoff ring.
      - if within the preferred band, keep it (STANDOFF_HOLD / TRACK).
      - if lock geometry is valid (interceptor at lock range from the TARGET), the base
        controller takes over (LOCK_READY).
    """

    def __init__(self, usv_speed=cfg.USV_SPEED, lock_range=cfg.LOCK_RANGE,
                 standoff=cfg.LOCK_RANGE * 0.85):
        self.usv_speed = usv_speed
        self.lock_range = lock_range
        self.standoff = standoff

    def plan(self, interceptor_name, interceptor_pos, corridor, break_x=cfg.BREAK_X):
        if corridor is None or interceptor_pos is None:
            return None
        tgt_cur = corridor.current_estimate
        vel = corridor.velocity
        # distance from interceptor to the target's CURRENT position
        d_cur = _dist(interceptor_pos, tgt_cur)
        # time-of-flight to the raw intercept point on the target's corridor
        t = max(1e-3, d_cur / self.usv_speed)
        px, py = tgt_cur
        for _ in range(4):
            tx = tgt_cur[0] + vel[0] * t
            ty = tgt_cur[1] + vel[1] * t
            px, py = tx, ty
            t = _dist(interceptor_pos, (px, py)) / self.usv_speed
        # STANDOFF PROJECTION: never drive inside the target's weapon band.
        dx, dy = tgt_cur[0] - px, tgt_cur[1] - py
        d_raw = math.hypot(dx, dy) or 1.0
        if d_raw < self.standoff:
            # raw intercept point is inside the band -> pull outward to the standoff ring
            px = tgt_cur[0] - dx / d_raw * self.standoff
            py = tgt_cur[1] - dy / d_raw * self.standoff
        # re-evaluate ETA to the final (projected) waypoint
        intercept_eta = _dist(interceptor_pos, (px, py)) / self.usv_speed
        target_d = _dist(tgt_cur, (px, py))
        target_speed = math.hypot(vel[0], vel[1]) or 1.0
        target_eta = target_d / target_speed
        margin = (target_eta - intercept_eta) / max(1.0, intercept_eta)
        feasible = margin >= -cfg.INTERCEPT_FEASIBLE_MARGIN
        # geometry state reflects the interceptor's ACTUAL position vs the target:
        #   - inside the standoff band -> pull outward (never knife-fight)
        #   - in [standoff, lock_range] with valid lock geometry -> base controller takes over
        #   - otherwise approach / hold at the projected band
        if d_cur < self.standoff:
            state = "REPOSITION_OUTWARD"
        elif d_cur <= self.lock_range and feasible:
            state = "LOCK_READY"
        elif d_raw <= self.lock_range:
            state = "STANDOFF_HOLD"
        else:
            state = "INTERCEPT_APPROACH"
        return InterceptPlan(corridor.track_name, interceptor_name, (px, py),
                             intercept_eta, target_eta, feasible, margin, state)
