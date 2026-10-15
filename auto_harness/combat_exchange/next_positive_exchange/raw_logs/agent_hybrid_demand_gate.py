#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""agent_hybrid_demand_gate.py — C9: TASK_DEMAND_GATED_COORDINATION.

Parent: ACE (agent_hybrid_allocator_expand.py). Candidate: white-combat-0009-v1.

Mechanism (ONE, minimal): same bounded 2-unit synchronized-lock package as C7, but FORM only under a
verified LOCAL TASK DEMAND — the target's single owner must currently be UNDER HOSTILE LOCK
(`is_locked` / `locked_attacker` non-empty), i.e. an adverse local engagement, not a transient healthy
state. Rationale (E2 evidence): W2-4 owners are almost never hostile-locked (sum 8) yet C7 formed ~15
packages/episode there and regressed a winning engagement, whereas W2-6 owners are frequently
hostile-locked (sum 40) and C7's packages helped. Gating formation on hostile-lock demand should keep
the W2-6 gain while protecting ACE's stable winning behaviour on W2-4.

UNCHANGED: ACE allocator/assignment, TrackManager, sensors, lock/fire legality, ActionSafety, Black,
simulator. NO truth, NO route/strategy-ID, NO LLM. Non-trigger behaviour == ACE by construction.
"""
import atexit
import json
import math
import os
import sys

from agent_hybrid_allocator_expand import ExpandAgentMain
from agent_hybrid_v5 import USVController, USV_SPEED, bearing_to, _KILLED

POLICY_ID = "white-combat-0009-v1"
PARENT = "ACE(white-combat-0002-v1)"
MECHANISM = "TASK_DEMAND_GATED_COORDINATION"

PACKAGE_MAX = 2
SYNC_RADIUS = 150_000.0
TTFL_GAP_SLOW = 60.0
MAX_SYNC_TIME = 1200.0
REQUIRE_HOSTILE_LOCK = True      # the demand gate


class DemandGateController(USVController):
    def __init__(self):
        super().__init__()
        self._pkg = {}
        self.package_events = []
        _log = os.environ.get("C9_PKG_LOG") or os.environ.get("C7_PKG_LOG")
        if _log:
            atexit.register(self._dump_packages, _log)

    def _dump_packages(self, path):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.package_events, f, ensure_ascii=False)
        except Exception:
            pass

    def _owners(self):
        m = {}
        for u, t in self.targets.items():
            if t:
                m.setdefault(t, []).append(u)
        return m

    def _free(self, obs):
        return [u for u in obs.usvs if u.get("is_alive") and u.get("position")
                and not self.targets.get(u["name"])]

    def _under_hostile_lock(self, obs, name):
        for u in obs.usvs:
            if u.get("name") == name:
                return bool(u.get("is_locked")) or bool(u.get("locked_attacker"))
        return False

    def _ttfl(self, upos, tpos):
        if upos is None or tpos is None:
            return None
        return math.hypot(tpos[0] - upos[0], tpos[1] - upos[1]) / max(1.0, USV_SPEED)

    def step(self, obs, tracks, legal, alloc_result, events, intent=None, mission=None):
        actions = super().step(obs, tracks, legal, alloc_result, events, intent, mission)
        now = obs.now
        owners = self._owners()
        free = self._free(obs)
        pos = {u["name"]: (u["position"][0], u["position"][1]) for u in obs.usvs
               if u.get("is_alive") and u.get("position")}

        def _drop(name):
            return [a for a in actions if a[0].split(" ", 1)[0] != name]

        for tname in list(self._pkg.keys()):
            pk = self._pkg[tname]
            t = tracks.get(tname)
            members_alive = [m for m in (pk["lead"], pk.get("support")) if m and m in pos]
            if (t is None or tname in _KILLED or not members_alive
                    or now - pk["t0"] > MAX_SYNC_TIME
                    or any(self.state.get(m) == self.LOCKING for m in members_alive)):
                _reason = ("member_locked" if any(self.state.get(m) == self.LOCKING for m in members_alive)
                           else "expired" if now - pk["t0"] > MAX_SYNC_TIME else "gone")
                self.package_events.append(("DISSOLVE", tname, round(now - pk["t0"], 1), _reason))
                del self._pkg[tname]

        for tname, t in tracks.items():
            if tname in _KILLED or not t.is_ship or not t.has_position or len(self._pkg) >= 4:
                continue
            if tname in self._pkg:
                continue
            ows = owners.get(tname, [])
            if len(ows) != 1:
                continue
            lead = ows[0]
            if self.state.get(lead) == self.LOCKING:
                continue
            # ---- DEMAND GATE: only coordinate when the owner is actually under hostile lock ----
            if REQUIRE_HOSTILE_LOCK and not self._under_hostile_lock(obs, lead):
                continue
            tpos = t.predicted_position(now)
            if tpos is None or not t.is_visible(now):
                continue
            cands = [u["name"] for u in free if u["name"] != lead
                     and math.hypot(pos[u["name"]][0] - tpos[0], pos[u["name"]][1] - tpos[1]) <= SYNC_RADIUS]
            if not cands:
                continue
            cands.sort(key=lambda n: (math.hypot(pos[n][0] - tpos[0], pos[n][1] - tpos[1]), n))
            support = cands[0]
            self._pkg[tname] = {"lead": lead, "support": support, "t0": now, "state": "SYNC_APPROACH"}
            _sp = abs((self._ttfl(pos[lead], tpos) or 0.0) - (self._ttfl(pos[support], tpos) or 0.0))
            self.package_events.append(("FORM", tname, lead, support, round(_sp, 1), round(now, 1)))
            self.targets[support] = tname
            actions = _drop(support)
            actions.append(self._move(support, pos[support], tpos))

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
                actions = _drop(lead)
                crs = bearing_to(pos[lead], tpos)
                actions.append((f"{lead} 移动 target_speed={USV_SPEED * 0.5:.1f} target_course={crs:.1f}", "move"))
        return actions


class DemandGateAgentMain(ExpandAgentMain):
    def __init__(self, use_uavs=True, max_steps=40000):
        super().__init__(use_uavs=use_uavs, max_steps=max_steps)
        self.usv_ctrl = DemandGateController()


if __name__ == "__main__":
    use_uavs = True
    for a in sys.argv[1:]:
        if a == "--no-uav":
            use_uavs = False
    DemandGateAgentMain(use_uavs=use_uavs).run()
