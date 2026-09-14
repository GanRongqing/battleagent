# -*- coding: utf-8 -*-
"""w7_performance_push/gap/w7_gap.py — W7-gap-a combat capacity-hole prevention.

Prevents 0-capacity holes BEFORE they become emergencies: if a RISING (medium-but-closing)
ship track has NO effective interceptor (no committed platform whose plan ETA is feasible
in-time) and a FREE USV exists, pre-commit the best FREE USV to that corridor. WHO/TARGET only;
USV controller/HOW = W5; FREE-only (no SOFT/HARD reassignment).
"""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from agent_hybrid_v5 import AgentMain, ThreatAllocator, _KILLED  # noqa: E402
from anti_evasion import config as cfg                          # noqa: E402

RISING_SCORE_LO = 1.6     # MEDIUM-ish threat (allocator scale); below HIGH(3.0)
RISING_SCORE_HI = 2.6     # below HIGH tier; not yet emergency


def is_rising_hole(t, now, threat, eta_feasible_committed):
    """Ship that is closing on White (moving -x), medium risk, and has NO committed in-time
    interceptor -> an emerging 0-capacity hole."""
    if not t.is_ship or not t.has_position or t.name in _KILLED:
        return False
    vel = t.last_velocity
    if not vel or vel[0] >= 0:      # not closing (moving away/static) -> no penetration hole
        return False
    score = threat(t, now)
    if not (RISING_SCORE_LO <= score < RISING_SCORE_HI):
        return False
    # 0 effective capacity: no committed interceptor that is feasible in-time
    return not eta_feasible_committed(t.name)


class GapPreventionAllocator:
    def __init__(self):
        self.base = ThreatAllocator()
        self.precommit_events = 0
        self.noop = 0

    def _eta_feasible_committed(self, alloc, tracks, usv_positions, now, name):
        r = None
        for t in tracks.values():
            if t.name == name:
                r = t
        if r is None:
            return False
        for u in alloc.get(name, []):
            p = usv_positions.get(u)
            if p is None:
                continue
            tp = r.predicted_position(now)
            if tp is None:
                continue
            d = math.hypot(p[0] - tp[0], p[1] - tp[1])
            eta = d / 20.0   # USV_SPEED
            b = None
            # approximate breakthrough horizon from position
            if tp[0] > cfg.BREAK_X and r.last_velocity and r.last_velocity[0] < 0:
                b = (tp[0] - cfg.BREAK_X) / (-r.last_velocity[0])
            if b is not None and b > 0 and eta * (1 + cfg.SCREEN_ETA_SAFETY) <= b:
                return True
            if b is None:
                return True
        return False

    def allocate_usvs(self, tracks, usvs, usv_map, now, intent=None, return_margin=False,
                      candidates=None):
        result = self.base.allocate_usvs(tracks, usvs, usv_map, now, intent=intent,
                                         return_margin=False, candidates=None)
        alloc = {t: list(u) for t, u in result.items()}
        committed = {u for vv in alloc.values() for u in vv}
        usv_positions = {u["name"]: tuple(u["position"][:2]) for u in usvs
                         if u.get("is_alive") and u.get("position")}
        free = [u for u in usv_positions if u not in committed]
        if not free:
            if return_margin:
                return alloc, None
            return alloc
        threat = lambda t, n: self.base.threat_score(t, n)
        holes = []
        for name, t in tracks.items():
            if is_rising_hole(t, now, threat,
                              lambda n: self._eta_feasible_committed(alloc, tracks,
                                                                     usv_positions, now, n)):
                holes.append((threat(t, now), name, t))
        holes.sort(key=lambda x: -x[0])
        done = False
        for score, name, t in holes[:1]:
            if not done:
                tp = t.predicted_position(now)
                if tp is None:
                    continue
                def dist(u):
                    p = usv_positions.get(u)
                    return math.hypot(p[0] - tp[0], p[1] - tp[1]) if p else 1e18
                best = min(free, key=dist)
                alloc.setdefault(name, []).append(best)
                free.remove(best)
                self.precommit_events += 1
                done = True
        if return_margin:
            return alloc, None
        return alloc

    def threat_score(self, t, now, intent=None, usvs=None):
        return self.base.threat_score(t, now, intent=intent, usvs=usvs)

    @property
    def low_conf_commitments(self):
        return self.base.low_conf_commitments

    @low_conf_commitments.setter
    def low_conf_commitments(self, v):
        self.base.low_conf_commitments = v


class W7GapAAgent(AgentMain):
    def __init__(self, use_uavs=True, max_steps=40000):
        super().__init__(use_uavs=use_uavs, max_steps=max_steps)
        self.allocator = GapPreventionAllocator()
