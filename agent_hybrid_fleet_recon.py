#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""agent_hybrid_fleet_recon.py — C25: FLEET_TETHERED_RECON.

Parent: C19 (agent_hybrid_press_search.py). Candidate: white-combat-0025-v1.

E24 P0 (verified): at Black's first lock (t=10406 s) in W2-1 all 5 surviving UAVs (battery 58%) are at
x≈46–126, y≈160–264 km — 220–325 km behind/north of the fleet front (all 20 USVs at x≈268, y≈0) — because
they follow the north-biased CoverageMap / GLOBAL_SEARCH. Their 60 km forward radar therefore cannot see the
engagement zone, so White USVs don't get positions in time to lock before Black's 300 s windows complete.
A UAV can reach a forward tether in ~2300 s (< 10406 s) => physically feasible.

Mechanism (ONE): while a UAV is in SEARCH / SCREEN / GLOBAL_SEARCH, tether it to a point ~30 km ahead of
the fleet's forward-most USV, spread across the fleet's y, instead of the coverage-grid target. RETURN /
LANDING / CHARGING / battery safety are untouched; only the recon target is replaced. No scenario/route ID,
no truth, no black-state read; C19 USV behaviour unchanged.
"""
import sys

from agent_hybrid_press_search import PressSearchAgentMain
from agent_hybrid_v5 import UAVManager, UAV_FLY_SPEED, bearing_to

POLICY_ID = "white-combat-0025-v1"
PARENT = "C19(white-combat-0019-v1)"
MECHANISM = "FLEET_TETHERED_RECON"
FRONT_OFFSET = 30_000.0
Y_SPREAD = 30_000.0


class FleetTetheredUAVManager(UAVManager):
    def _tether_points(self, usvs, n):
        fx = max(u["position"][0] for u in usvs)
        fy = sum(u["position"][1] for u in usvs) / len(usvs)
        pts = []
        for i in range(n):
            frac = 0.0 if n <= 1 else (i - (n - 1) / 2.0) / ((n - 1) / 2.0)
            pts.append((fx + FRONT_OFFSET, fy + frac * Y_SPREAD))
        return pts

    def step(self, obs, tracker, legal, events, intent=None, threat_fn=None,
             coverage=None, mission=None):
        actions = super().step(obs, tracker, legal, events, intent, threat_fn, coverage, mission)
        usvs = [u for u in obs.usvs if u.get("is_alive") and u.get("position")]
        alive = [u for u in obs.uavs if u.get("is_alive") and u.get("position")]
        if not usvs or not alive:
            return actions
        pts = self._tether_points(usvs, len(alive))
        for u, (tx, ty) in zip(sorted(alive, key=lambda z: z["name"]), pts):
            st = self.state.get(u["name"])
            if st not in (self.SEARCH, self.SCREEN, self.GLOBAL_SEARCH):
                continue
            if not legal.can_fly(u["name"]):
                continue
            x, y = u["position"][0], u["position"][1]
            crs = bearing_to((x, y), (tx, ty))
            actions = [a for a in actions if a[0].split(" ", 1)[0] != u["name"]]
            actions.append((f'{u["name"]} 飞行 target_speed={UAV_FLY_SPEED:.1f} target_course={crs:.1f}', "fly"))
        return actions


class FleetReconAgentMain(PressSearchAgentMain):
    def __init__(self, use_uavs=True, max_steps=40000):
        super().__init__(use_uavs=use_uavs, max_steps=max_steps)
        self.uav_mgr = FleetTetheredUAVManager(enabled=use_uavs)


if __name__ == "__main__":
    use_uavs = True
    for a in sys.argv[1:]:
        if a == "--no-uav":
            use_uavs = False
    FleetReconAgentMain(use_uavs=use_uavs).run()
