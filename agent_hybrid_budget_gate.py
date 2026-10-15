#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""agent_hybrid_budget_gate.py — C10: BUDGETED_COORDINATION.

Parent: ACE (agent_hybrid_allocator_expand.py). Candidate: white-combat-0010-v1.

Mechanism (ONE, minimal): identical to C7's bounded 2-unit synchronized-lock package, but the number of
packages formed per episode is capped by a small global budget (MAX_TOTAL_PACKAGES = 3).

Rationale (E2 evidence): on W2-6 C7 formed ~2 packages/episode and improved (own-lock 11->15, ratio
0.556->0.688); on W2-4 C7 formed ~15 packages/episode and regressed a winning engagement (2.000->1.366,
wins 5/5->3/5). A small cumulative budget limits unnecessary coordination interference while keeping the
few helpful packages.

UNCHANGED: ACE allocator/assignment, TrackManager, sensors, lock/fire legality, ActionSafety, Black,
simulator. NO truth, NO route/strategy-ID, NO LLM. Before the budget is exhausted behaviour is C7-like;
once exhausted behaviour is exactly ACE.
"""
import atexit
import json
import math
import os
import sys

from agent_hybrid_allocator_expand import ExpandAgentMain
from agent_hybrid_v5 import USVController, USV_SPEED, bearing_to, _KILLED

POLICY_ID = "white-combat-0010-v1"
PARENT = "ACE(white-combat-0002-v1)"
MECHANISM = "BUDGETED_COORDINATION"

PACKAGE_MAX = 2
SYNC_RADIUS = 150_000.0
TTFL_GAP_SLOW = 60.0
MAX_SYNC_TIME = 1200.0
MAX_TOTAL_PACKAGES = 3          # the budget (one conservative engineering choice)


class BudgetGateController(USVController):
    def __init__(self):
        super().__init__()
        self._pkg = {}
        self._formed_total = 0
        self.package_events = []
        _log = os.environ.get("C10_PKG_LOG") or os.environ.get("C7_PKG_LOG")
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
            if self._formed_total >= MAX_TOTAL_PACKAGES:      # ---- budget exhausted: ACE only ----
                break
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
            self._formed_total += 1
            _sp = abs((self._ttfl(pos[lead], tpos) or 0.0) - (self._ttfl(pos[support], tpos) or 0.0))
            self.package_events.append(("FORM", tname, lead, support, round(_sp, 1), round(now, 1),
                                        self._formed_total))
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


class BudgetGateAgentMain(ExpandAgentMain):
    def __init__(self, use_uavs=True, max_steps=40000):
        super().__init__(use_uavs=use_uavs, max_steps=max_steps)
        self.usv_ctrl = BudgetGateController()


if __name__ == "__main__":
    use_uavs = True
    for a in sys.argv[1:]:
        if a == "--no-uav":
            use_uavs = False
    BudgetGateAgentMain(use_uavs=use_uavs).run()
