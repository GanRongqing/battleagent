#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""adaptive_skills.py — E25 executable Skill Registry + Situation Features + Adaptive Composer.

Only uses legal observations/derived history (obs.usvs/uavs/passive, TrackManager tracks, sim time).
No scenario name/ID, no seed, no black truth, no fixed enemy route. Skills are axis-independent:
  USV maneuver : ACTIVE_SEARCH | DEFENSIVE_SCREEN | CONTACT_MAINTENANCE | POSITION_RECOVERY
  UAV recon    : FLEET_TETHERED_RECON | BROAD_SEARCH | SAFE_RETURN (owned by UAV FSM)
  Engagement   : COOPERATIVE_ALLOCATION (existing C10 allocator/lock path, unchanged)
"""
import math
import os
import atexit
import json
from dataclasses import dataclass

AREA = (0.0, 370_400.0, -277_800.0, 277_800.0)
RECOVERY_MARGIN = 40_000.0


@dataclass
class SituationFeatures:
    active: int
    passive: int
    usv_alive: int
    usv_locking: int
    usv_frozen: int
    uav_alive: int
    uav_forward: int
    boundary_margin: float
    fleet_spread: float
    has_threat: bool


def extract(obs, tracks, now):
    vis = [t for t in tracks.values()
           if getattr(t, "has_position", False) and getattr(t, "is_visible", lambda _n: False)(now)]
    active = len(vis)
    passive = len(getattr(obs, "passive", None) or [])
    usv_alive = sum(1 for u in obs.usvs if u.get("is_alive"))
    usv_locking = sum(1 for u in obs.usvs if u.get("is_locking"))
    usv_frozen = sum(1 for u in obs.usvs if u.get("is_frozen"))
    uav_alive = sum(1 for u in obs.uavs if u.get("is_alive"))
    us = [u for u in obs.usvs if u.get("is_alive") and u.get("position")]
    xs = [u["position"][0] for u in us]
    ys = [u["position"][1] for u in us]
    x0, x1, y0, y1 = AREA
    if xs:
        fx = max(xs)
        uav_forward = sum(1 for u in obs.uavs
                          if u.get("is_alive") and u.get("position") and u["position"][0] >= fx)
        margin = min(min(x - x0, x1 - x, y - y0, y1 - y) for x, y in zip(xs, ys))
        spread = max(xs) - min(xs)
    else:
        uav_forward = 0
        margin = 0.0
        spread = 0.0
    return SituationFeatures(active, passive, usv_alive, usv_locking, usv_frozen,
                             uav_alive, uav_forward, margin, spread, active > 0)


class Composer:
    """Deterministic per-axis composer with hysteresis on the USV axis."""

    HOLD = 3

    def __init__(self):
        self.usv_mode = "ACTIVE_SEARCH"
        self.uav_mode = "FLEET_TETHERED_RECON"
        self._pending = 0
        self.trace = []
        if os.environ.get("SKILL_TRACE"):
            atexit.register(self._dump_trace)

    def _dump_trace(self):
        try:
            with open(os.environ["SKILL_TRACE"], "a", encoding="utf-8") as f:
                f.write(json.dumps(self.trace, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def decide(self, f, now=None):
        want = ("POSITION_RECOVERY" if f.boundary_margin < RECOVERY_MARGIN
                else "CONTACT_MAINTENANCE" if f.has_threat else "ACTIVE_SEARCH")
        if want != self.usv_mode:
            self._pending += 1
            if self._pending >= self.HOLD:
                self.usv_mode = want
                self._pending = 0
        else:
            self._pending = 0
        self.uav_mode = "BROAD_SEARCH" if f.has_threat else "FLEET_TETHERED_RECON"
        self.trace.append((now, self.usv_mode, self.uav_mode))
        return self.usv_mode, self.uav_mode
