#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""agent_hybrid_passive_isolated.py — E17: Track-Only + C16 RESOURCE_AWARE_PASSIVE_RECOVERY.

Parent: C10 (agent_hybrid_budget_gate.py).

Fixes C15's two problems:
  1. Structured passive history bound to the observing platform (bearing + detector position + time +
     source), so a later alert cannot overwrite another observer's geometry and stale alerts expire.
  2. Resource-aware localisation: a scout is chosen ONLY among UAVs whose controller state is SEARCH
     (never RETURN/LANDING/SCREEN/REACQUIRE/battery-critical), never by a fixed UAV name, and only when
     >=2 UAVs are alive. If no eligible scout exists, the original actions are returned unchanged.

TrackOnlyAgentMain = C10 + PassiveHistoryManager only (no extra actions).
PassiveIsolatedAgentMain = C16 (adds the resource-aware localizer).
"""
import math
import sys

from agent_hybrid_budget_gate import BudgetGateAgentMain
from agent_hybrid_v5 import TrackManager, UAVManager

TRACK_ONLY_ID = "white-combat-0016-trackonly"
POLICY_ID = "white-combat-0016-v1"
PARENT = "C10(white-combat-0010-v1)"
MECHANISM = "RESOURCE_AWARE_PASSIVE_RECOVERY"
LOCALIZE_MAX_AGE = 600.0
HISTORY_CAP = 64
SCOUT_AIM = 60_000.0


class PassiveHistoryManager(TrackManager):
    """TrackManager + a bounded, platform-bound passive-observation history (no position fabrication)."""

    def __init__(self):
        super().__init__()
        self.passive_history = {}     # name -> [ {t, bearing, detected_by, detector_pos, source} ]
        self.passive_best = {}        # name -> latest record

    def _record(self, obs, p):
        nm = p.get("name"); db = p.get("detected_by")
        if not nm:
            return
        dpos = None
        for u in obs.usvs:
            if u.get("name") == db and u.get("position"):
                dpos = (u["position"][0], u["position"][1]); break
        rec = {"t": obs.now, "bearing": p.get("bearing"), "detected_by": db,
               "detector_pos": dpos, "source": p.get("source", "被动告警")}
        hist = self.passive_history.setdefault(nm, [])
        # duplicate handling: same (t, bearing, detected_by) is one observation
        key = (rec["t"], rec["bearing"], rec["detected_by"])
        if any((h["t"], h["bearing"], h["detected_by"]) == key for h in hist[-3:]):
            return
        hist.append(rec)
        if len(hist) > HISTORY_CAP:
            del hist[0]
        self.passive_best[nm] = rec

    def update(self, obs):
        # IMPORTANT (E17): record history in a SEPARATE structure and DO NOT mutate the base track
        # lifecycle (last_seen_time/bearing). Mutating freshness changes reacquire/drop consumers and
        # makes the "data-only" fix non-neutral (verified: TrackOnly regressed W2-5 to 16/17).
        for p in obs.passive or []:
            self._record(obs, p)
        return super().update(obs)

    def localize_candidates(self, now, max_age=LOCALIZE_MAX_AGE):
        out = []
        for nm, rec in self.passive_best.items():
            t = self.tracks.get(nm)
            if t is None or getattr(t, "has_position", False):
                continue
            if rec.get("bearing") is None or rec.get("detector_pos") is None:
                continue
            age = now - rec["t"]
            if age < 0 or age > max_age:
                continue
            out.append((age, nm, rec))
        out.sort(key=lambda x: (x[0], x[1]))
        return out


class ResourceAwareLocalizeUAVManager(UAVManager):
    def step(self, obs, tracker, legal, events, intent=None, threat_fn=None, coverage=None, mission=None):
        actions = super().step(obs, tracker, legal, events, intent, threat_fn, coverage, mission)
        if not hasattr(tracker, "localize_candidates"):
            return actions
        cands = tracker.localize_candidates(obs.now)
        if not cands:
            return actions
        alive = [u for u in obs.uavs if u.get("is_alive") and not u.get("is_at_usv") and u.get("position")]
        if len(alive) < 2:
            return actions
        # eligible scout: controller state == SEARCH (idle search) only; deterministic order; no fixed name
        eligible = [u for u in alive if self.state.get(u.get("name")) == self.SEARCH]
        if not eligible:
            return actions
        eligible.sort(key=lambda u: u["name"])
        scout = eligible[0]
        age, nm, rec = cands[0]
        dp = rec["detector_pos"]; brg = float(rec["bearing"])
        rad = math.radians(brg)
        aim = (dp[0] + SCOUT_AIM * math.sin(rad), dp[1] + SCOUT_AIM * math.cos(rad))
        pos = (scout["position"][0], scout["position"][1])
        actions = [a for a in actions if a[0].split(" ", 1)[0] != scout["name"]]
        actions.append(self._fly(scout["name"], pos, aim))
        return actions


class TrackOnlyAgentMain(BudgetGateAgentMain):
    def __init__(self, use_uavs=True, max_steps=40000):
        super().__init__(use_uavs=use_uavs, max_steps=max_steps)
        self.tracker = PassiveHistoryManager()


class PassiveIsolatedAgentMain(BudgetGateAgentMain):
    def __init__(self, use_uavs=True, max_steps=40000):
        super().__init__(use_uavs=use_uavs, max_steps=max_steps)
        self.tracker = PassiveHistoryManager()
        self.uav_mgr = ResourceAwareLocalizeUAVManager(enabled=use_uavs)


if __name__ == "__main__":
    use_uavs = True
    for a in sys.argv[1:]:
        if a == "--no-uav":
            use_uavs = False
    PassiveIsolatedAgentMain(use_uavs=use_uavs).run()
