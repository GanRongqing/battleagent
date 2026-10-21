#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""agent_hybrid_passive_recovery.py — C15: PASSIVE_OBSERVATION_RECOVERY.

Parent: C10 (agent_hybrid_budget_gate.py). Candidate: white-combat-0015-v1.

Verified defect (E16 P0): `TrackManager.update` creates a bearing-only track on the first passive alert
but never refreshes `bearing`/`last_seen_time` for an existing one, and bearing-only tracks never enter any
decision branch. So passive contacts (e.g. W2-5 usv4: 10 passive alerts, 0 radar-positioned) are effectively
lost and can never be localised.

Mechanism (ONE, minimal): (1) a PassiveAwareTrackManager that faithfully refreshes bearing-only tracks
(bearing, last_seen_time, detector identity) without ever promoting them to a positioned track; (2) a single
designated scout UAV that, while a fresh bearing-only alert exists, flies along that **absolute bearing**
toward the emitter to acquire a radar contact (only when >=2 UAVs are alive, so screen coverage is kept).

Uses only legal `obs.passive{name,bearing,detected_by}` + own positions. No truth, no scenario/route/
strategy ID. Lock/fire/weapon/radar semantics unchanged (radar acquisition is done by the real sensor when
the scout arrives).
"""
import math
import sys

from agent_hybrid_budget_gate import BudgetGateAgentMain
from agent_hybrid_v5 import TrackManager, UAVManager

POLICY_ID = "white-combat-0015-v1"
PARENT = "C10(white-combat-0010-v1)"
MECHANISM = "PASSIVE_OBSERVATION_RECOVERY"
LOCALIZE_MAX_AGE = 900.0
SCOUT_AIM = 60_000.0


class PassiveAwareTrackManager(TrackManager):
    def __init__(self):
        super().__init__()
        self.passive_detectors = {}   # name -> set(detected_by)

    def update(self, obs):
        now = obs.now
        # refresh EXISTING bearing-only tracks before the base drop/age logic runs
        for p in obs.passive or []:
            nm = p.get("name")
            if not nm:
                continue
            t = self.tracks.get(nm)
            if t is not None and not getattr(t, "has_position", False):
                t.bearing = p.get("bearing")
                t.last_seen_time = now
                t.seen_count = getattr(t, "seen_count", 1) + 1
                db = p.get("detected_by")
                if db:
                    self.passive_detectors.setdefault(nm, set()).add(db)
        out = super().update(obs)
        for p in obs.passive or []:
            nm = p.get("name"); db = p.get("detected_by")
            if nm and db:
                self.passive_detectors.setdefault(nm, set()).add(db)
        return out


class PassiveLocalizeUAVManager(UAVManager):
    def step(self, obs, tracker, legal, events, intent=None, threat_fn=None, coverage=None, mission=None):
        actions = super().step(obs, tracker, legal, events, intent, threat_fn, coverage, mission)
        # localise at most ONE fresh bearing-only contact with a single scout UAV
        alive = [u for u in obs.uavs if u.get("is_alive") and not u.get("is_at_usv") and u.get("position")]
        if len(alive) < 2:
            return actions
        # deterministic scout: prefer white_uav10 if alive, else the last alive by name
        alive.sort(key=lambda u: u["name"])
        scout = next((u for u in alive if u["name"] == "white_uav10"), alive[-1])
        pos = (scout["position"][0], scout["position"][1])
        # freshest bearing-only track with a known detector
        best = None
        for nm, t in tracker.tracks.items():
            if getattr(t, "has_position", False):
                continue
            brg = getattr(t, "bearing", None)
            if brg is None:
                continue
            age = obs.now - getattr(t, "last_seen_time", obs.now)
            if age > LOCALIZE_MAX_AGE:
                continue
            det = getattr(tracker, "passive_detectors", {}).get(nm)
            if not det:
                continue
            best = (age, nm, float(brg), det)
            break
        if best is None:
            return actions
        age, nm, brg, det = best
        # aim along the absolute bearing from the DETECTING unit's own position (legal own history)
        upos = None
        for u in obs.usvs:
            if u.get("name") in det and u.get("position"):
                upos = (u["position"][0], u["position"][1]); break
        if upos is None:
            return actions
        rad = math.radians(brg)
        aim = (upos[0] + SCOUT_AIM * math.sin(rad), upos[1] + SCOUT_AIM * math.cos(rad))
        actions = [a for a in actions if a[0].split(" ", 1)[0] != scout["name"]]
        actions.append(self._fly(scout["name"], pos, aim))
        return actions


class PassiveRecoveryAgentMain(BudgetGateAgentMain):
    def __init__(self, use_uavs=True, max_steps=40000):
        super().__init__(use_uavs=use_uavs, max_steps=max_steps)
        self.tracker = PassiveAwareTrackManager()
        self.uav_mgr = PassiveLocalizeUAVManager(enabled=use_uavs)


if __name__ == "__main__":
    use_uavs = True
    for a in sys.argv[1:]:
        if a == "--no-uav":
            use_uavs = False
    PassiveRecoveryAgentMain(use_uavs=use_uavs).run()
