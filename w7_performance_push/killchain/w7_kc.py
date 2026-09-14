# -*- coding: utf-8 -*-
"""w7_performance_push/killchain/w7_kc.py — W7 kill-chain completion modules.

Base: frozen W5 (runtime untouched). A proxy ThreatAllocator runs the frozen W5 allocation,
then adds ONE follow-up USV to a HIGH/CRITICAL hit-frozen completion target. WHO/TARGET only;
USV controller/HOW unchanged; execution override = 0.

Legal hit-frozen signal: an ENGAGED ship track that is currently STATIONARY (velocity ~ 0),
i.e. inside the ~300 s hit-freeze window (White cannot see enemy damage truth).
"""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from agent_hybrid_v5 import AgentMain, ThreatAllocator, _KILLED  # noqa: E402

STATIONARY_SPEED = 2.0     # m/s threshold -> stationary = hit-frozen proxy (legal)
KC_MAX_ATTACKERS = 2       # per-target follow-up cap (scale-agnostic; not over-concentration)
HIGH_SCORE = 3.0           # threat_score HIGH tier (matches allocator scale)


def completion_targets(tracks, now, threat_fn):
    out = []
    for name, t in tracks.items():
        if not t.is_ship or not t.has_position or name in _KILLED:
            continue
        if not (t.engaged or t.assigned_usvs):
            continue
        if len(t.assigned_usvs) >= KC_MAX_ATTACKERS:
            continue
        vel = t.last_velocity
        speed = (vel[0] ** 2 + vel[1] ** 2) ** 0.5 if vel else 0.0
        if speed > STATIONARY_SPEED:
            continue
        risk = threat_fn(t, now) if threat_fn else 0.0
        if risk < HIGH_SCORE:
            continue
        out.append((risk, name, t))
    return out


class KillChainCompletionAllocator:
    """Proxy around the frozen W5 ThreatAllocator; adds completion follow-up afterwards."""

    def __init__(self):
        self.base = ThreatAllocator()
        self.frozen_candidates = 0
        self.completion_assignments = 0
        self.overconcentrated_blocks = 0

    def allocate_usvs(self, tracks, usvs, usv_map, now, intent=None, return_margin=False,
                      candidates=None):
        result = self.base.allocate_usvs(tracks, usvs, usv_map, now, intent=intent,
                                         return_margin=False, candidates=None)
        # build alloc dict and free pool
        alloc = {t: list(u) for t, u in result.items()}
        committed = {u for vv in alloc.values() for u in vv}
        usv_positions = {u["name"]: tuple(u["position"][:2]) for u in usvs
                         if u.get("is_alive") and u.get("position")}
        free = [u for u in usv_positions if u not in committed]
        threat = lambda t, n: self.base.threat_score(t, n) if hasattr(self.base, "threat_score") else 0.0
        if free:
            cands = completion_targets(tracks, now, threat)
            cands.sort(key=lambda x: -x[0])
            for risk, name, t in cands[:1]:
                assigned = alloc.get(name) or []
                if len(assigned) >= KC_MAX_ATTACKERS:
                    self.overconcentrated_blocks += 1
                    continue
                self.frozen_candidates += 1
                tp = t.predicted_position(now)
                if tp is None:
                    continue
                def dist(u):
                    p = usv_positions.get(u)
                    return math.hypot(p[0] - tp[0], p[1] - tp[1]) if p else 1e18
                best = min(free, key=dist)
                alloc.setdefault(name, []).append(best)
                free.remove(best)
                self.completion_assignments += 1
        if return_margin:
            return alloc, None
        return alloc

    # keep ThreatAllocator surface used elsewhere
    def threat_score(self, t, now, intent=None, usvs=None):
        return self.base.threat_score(t, now, intent=intent, usvs=usvs)

    @property
    def low_conf_commitments(self):
        return self.base.low_conf_commitments

    @low_conf_commitments.setter
    def low_conf_commitments(self, v):
        self.base.low_conf_commitments = v


class W7KcAAgent(AgentMain):
    """W5 + kill-chain completion overlay. Runtime (step_once) is inherited W5."""
    def __init__(self, use_uavs=True, max_steps=40000):
        super().__init__(use_uavs=use_uavs, max_steps=max_steps)
        self.allocator = KillChainCompletionAllocator()
