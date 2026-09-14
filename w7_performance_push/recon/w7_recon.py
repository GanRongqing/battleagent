# -*- coding: utf-8 -*-
"""w7_performance_push/recon/w7_recon.py — W7 recon-first module.

Base: frozen W5 (agent_hybrid_v5). Only UAV/sensing layer changes; USV allocator and USV
controller (HOW) untouched. Targets B3 pressure: dispersion / track loss / search burden /
evasion / multi-axis early discovery.

RECON-A levers (minimal, legal, scale-agnostic):
  1. recon_mode bias -> 'screen_priority' while combat not globally-resolving:
     lowers the SCREEN gate (0.25) so airborne UAVs maintain forward shared sensing on
     high/lane threats (evidence: screen protective; UAV sensing is the top discovery
     resource) -> earlier first-lock / first-discovery, less evasion by information gap.
  2. High-risk lost-track reacquire pre-seed: when a HIGH-risk ship track goes stale/lost,
     seed its reacquire_lock in risk order before the base step runs, so the base REACQUIRE
     machinery (region sweep, legal) reacquires the most breakthrough-dangerous first.
"""
from agent_hybrid_v5 import (AgentMain, UAVManager, UAV_BATTERY_TOTAL, MISSION_NORMAL,  # noqa
                             UAV_FLY_SPEED, bearing_to)
from agent_hybrid_v5 import _KILLED  # noqa

HIGH_RISK_SCORE = 3.0          # threat_score threshold ~ breakthrough-dangerous (see v5)
RECON_MODE_ON_RESOLVING = "screen_priority"
RECON_MODE_ON_COMBAT = "screen_priority"   # keep lanes watched during active combat too


class ReconUAVManager(UAVManager):
    def step(self, obs, tracker, legal, events, intent=None, threat_fn=None,
             coverage=None, mission=MISSION_NORMAL):
        now = obs.now
        # 2) pre-seed reacquire for lost high-risk ships (risk order) using legal belief
        if threat_fn is not None:
            lost_high = []
            for name, t in tracker.tracks.items():
                if not t.is_ship or not t.has_position or name in _KILLED:
                    continue
                if t.is_visible(now):
                    continue
                if threat_fn(t, now) >= HIGH_RISK_SCORE and t.name not in self.reacquire_lock:
                    lost_high.append(t)
            if lost_high and not self.reacquire_lock:
                free_uav = [u["name"] for u in obs.uavs
                            if u.get("is_alive") and self.state.get(u["name"]) in
                            (None, self.SEARCH, self.SAFE_LOITER)]
                if free_uav:
                    ordered = sorted(lost_high, key=lambda t: -threat_fn(t, now))
                    for t in ordered[:len(free_uav)]:
                        self.reacquire_lock[t.name] = free_uav[len(self.reacquire_lock)
                                                               if len(self.reacquire_lock) < len(free_uav) else 0]
        # 1) bias recon_mode toward screen while any airborne UAV exists
        if intent is not None:
            try:
                intent.recon_mode = RECON_MODE_ON_COMBAT
            except Exception:
                pass
        return super().step(obs, tracker, legal, events, intent=intent,
                            threat_fn=threat_fn, coverage=coverage, mission=mission)


class W7ReconAAgent(AgentMain):
    """W5 + recon-a (UAV screen bias + high-risk reacquire pre-seed). USV = W5 exactly."""
    def __init__(self, use_uavs=True, max_steps=40000):
        super().__init__(use_uavs=use_uavs, max_steps=max_steps)
        self.uav_mgr = ReconUAVManager(enabled=use_uavs)
