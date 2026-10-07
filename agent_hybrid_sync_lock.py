#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""agent_hybrid_sync_lock.py — C7: SYNCHRONIZED_LOCK_ACQUISITION.

Parent: ACE (agent_hybrid_allocator_expand.py). Candidate: white-combat-0008-v1.

Mechanism (ONE): bounded 2-unit (max 3) engagement PACKAGES that synchronize pre-lock approach
timing around a reachable known/assigned threat, so members reach own-lock geometry near
simultaneously — improving ASSIGNED/KNOWN THREAT -> ACTIVE OWN LOCK conversion.

UNCHANGED: ACE allocator/assignment, reserve, coverage, TrackManager, sensor semantics, lock/fire
legality, ActionSafety, Black, simulator. NO truth, NO route/strategy-ID, NO LLM, NO blanket speed-up.

Bounded: package size 2 (max 3); coverage floor preserved (never divert the last free USV covering an
actionable target); MAX_FORM_TIME / MAX_SYNC_TIME -> DISSOLVE; LEAD shaped (slowed) if ahead.
"""
import math
import sys

from agent_hybrid_allocator_expand import ExpandAgentMain
from agent_hybrid_v5 import USVController, USV_SPEED, bearing_to, _KILLED

POLICY_ID = "white-combat-0008-v1"
PARENT = "ACE(white-combat-0002-v1)"
MECHANISM = "SYNCHRONIZED_LOCK_ACQUISITION"

PACKAGE_MAX = 2
SYNC_RADIUS = 150_000.0     # m; support reachability
TTFL_GAP_SLOW = 60.0        # s; if lead TTFL + this < support TTFL, slow the lead
MAX_SYNC_TIME = 1200.0      # sim-s; bounded package lifetime


class SyncLockController(USVController):
    def __init__(self):
        super().__init__()
        self._pkg = {}          # target_name -> {"lead":u, "support":u, "t0":t, "state":s}
        self.package_events = []  # diagnostics

    # ---- helpers (legal-only) ----
    def _owners(self):
        m = {}
        for u, t in self.targets.items():
            if t:
                m.setdefault(t, []).append(u)
        return m

    def _free(self, obs):
        return [u for u in obs.usvs if u.get("is_alive") and u.get("position")
                and not self.targets.get(u["name"])]

    def _ttfl(self, upos, tpos):
        if upos is None or tpos is None:
            return None
        return math.hypot(tpos[0] - upos[0], tpos[1] - upos[1]) / max(1.0, USV_SPEED)

    def step(self, obs, tracks, legal, alloc_result, events, intent=None, mission=None):
        # ACE does the full allocation; self.targets is overwritten by super() (line 2105).
        actions = super().step(obs, tracks, legal, alloc_result, events, intent, mission)
        now = obs.now
        owners = self._owners()
        free = self._free(obs)
        pos = {u["name"]: (u["position"][0], u["position"][1]) for u in obs.usvs
               if u.get("is_alive") and u.get("position")}

        def _drop(name):
            return [a for a in actions if a[0].split(" ", 1)[0] != name]

        # dissolve finished/expired packages
        for tname in list(self._pkg.keys()):
            pk = self._pkg[tname]
            t = tracks.get(tname)
            members_alive = [m for m in (pk["lead"], pk.get("support")) if m and m in pos]
            if (t is None or tname in _KILLED or not members_alive
                    or now - pk["t0"] > MAX_SYNC_TIME
                    or any(self.state.get(m) == self.LOCKING for m in members_alive)):
                self.package_events.append(("DISSOLVE", tname, round(now - pk["t0"], 1)))
                del self._pkg[tname]

        # form packages for single-owner unlocked actionable targets
        for tname, t in tracks.items():
            if tname in _KILLED or not t.is_ship or not t.has_position or len(self._pkg) >= 4:
                continue
            if tname in self._pkg:
                continue
            ows = owners.get(tname, [])
            if len(ows) != 1:
                continue                      # only exactly-1-owner targets
            lead = ows[0]
            if self.state.get(lead) == self.LOCKING:
                continue
            tpos = t.predicted_position(now)
            if tpos is None or not t.is_visible(now):
                continue
            # coverage-floor invariant: only divert a FREE USV; never an owner of another target
            cands = [u["name"] for u in free if u["name"] != lead
                     and math.hypot(pos[u["name"]][0] - tpos[0], pos[u["name"]][1] - tpos[1]) <= SYNC_RADIUS]
            if not cands:
                continue
            # deterministic selection: nearest, tie-break by id
            cands.sort(key=lambda n: (math.hypot(pos[n][0] - tpos[0], pos[n][1] - tpos[1]), n))
            support = cands[0]
            self._pkg[tname] = {"lead": lead, "support": support, "t0": now, "state": "SYNC_APPROACH"}
            self.package_events.append(("FORM", tname, lead, support))
            # redirect the support to this target + approach
            self.targets[support] = tname
            actions = _drop(support)
            actions.append(self._move(support, pos[support], tpos))

        # synchronize: slow the lead if it would arrive far earlier than its support
        for tname, pk in self._pkg.items():
            lead, sup = pk["lead"], pk.get("support")
            if not lead or not sup or lead not in pos or sup not in pos:
                continue
            t = tracks.get(tname)
            if t is None:
                continue
            tpos = t.predicted_position(now)
            if tpos is None:
                continue
            tl = self._ttfl(pos[lead], tpos)
            ts = self._ttfl(pos[sup], tpos)
            if tl is not None and ts is not None and (ts - tl) > TTFL_GAP_SLOW:
                # bounded shaping: reduce lead forward speed (no retreat, no stop)
                actions = _drop(lead)
                crs = bearing_to(pos[lead], tpos)
                actions.append((f"{lead} 移动 target_speed={USV_SPEED * 0.5:.1f} target_course={crs:.1f}", "move"))
        return actions


class SyncLockAgentMain(ExpandAgentMain):
    def __init__(self, use_uavs=True, max_steps=40000):
        super().__init__(use_uavs=use_uavs, max_steps=max_steps)
        self.usv_ctrl = SyncLockController()


if __name__ == "__main__":
    use_uavs = True
    for a in sys.argv[1:]:
        if a == "--no-uav":
            use_uavs = False
    SyncLockAgentMain(use_uavs=use_uavs).run()
