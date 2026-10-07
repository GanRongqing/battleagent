#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""agent_hybrid_track_reacquire.py — C5: TRACK_AWARE_REACQUISITION.

Parent: ACE (agent_hybrid_allocator_expand.py). Candidate: white-combat-0005-v1.

Mechanism (ONE): for an ASSIGNED USV whose target is stale-but-present BEFORE its first effective
engagement, retain bounded ownership and drive an INTERCEPT move from a small deterministic predictor
bank; end on re-observation (FRESH), uncertainty threshold (EXPIRED), or timeout (EXPIRED). On EXPIRED
the parent (ACE) semantics are used unchanged.

UNCHANGED: allocator, reserve release, coverage, lock legality, fire legality, retreat, survival,
kill-closure.
CHANGED: stale-window MOVE for assigned USVs only (predictor-bank intercept + explicit bound).
When every assigned target is FRESH this is an EXACT no-op vs ACE.

Legality: prediction drives MOVE only; LOCK/FIRE stay governed by observed legal actions + ActionSafety.
"""
import math
import sys

from agent_hybrid_allocator_expand import ExpandAgentMain
from agent_hybrid_v5 import USVController, USV_SPEED, bearing_to, _KILLED

POLICY_ID = "white-combat-0006-v1"
PARENT = "ACE(white-combat-0002-v1)"
MECHANISM = "TRACK_AWARE_REACQUISITION"

MAX_REACQUIRE_TIME = 900.0    # sim-s stale window before EXPIRED (conservative; no search)
U_MAX = 40_000.0              # m; track uncertainty radius cap -> EXPIRED (reuses t.uncertainty)
EMA_ALPHA = 0.3


class _PredictorBank:
    """Deterministic predictor bank: P0 constant-velocity, P1 recent-velocity, P2 turn-aware."""

    def __init__(self):
        self.err = {}      # (name, pred_id) -> EMA error
        self.recent = {}   # name -> [(t,x,y), ...]

    def observe(self, name, t, x, y):
        lst = self.recent.setdefault(name, [])
        lst.append((t, x, y))
        if len(lst) > 8:
            del lst[:-8]

    def predict(self, name, t, track):
        lp, lv = track.last_position, track.last_velocity
        preds = {}
        if lp is not None and lv is not None:
            dt = max(0.0, t - track.last_seen_time)
            preds["P0"] = (lp[0] + lv[0] * dt, lp[1] + lv[1] * dt)
        rec = self.recent.get(name, [])
        if len(rec) >= 2 and rec[-1][0] > rec[0][0]:
            (t0, x0, y0), (t1, x1, y1) = rec[0], rec[-1]
            vx, vy = (x1 - x0) / (t1 - t0), (y1 - y0) / (t1 - t0)
            dt = max(0.0, t - t1)
            preds["P1"] = (x1 + vx * dt, y1 + vy * dt)
            if getattr(track, "maneuver_score", 0.0) >= 0.5:
                preds["P2"] = (x1 + vx * dt, y1 + vy * dt)
        if not preds:
            return (None, None, "NONE")
        best = min(preds, key=lambda p: self.err.get((name, p), float("inf")))
        if self.err.get((name, best), float("inf")) == float("inf"):
            best = "P0" if "P0" in preds else next(iter(preds))
        return (preds[best][0], preds[best][1], best)

    def score(self, name, pred_id, predicted, observed):
        if predicted is None or pred_id in (None, "NONE"):
            return
        e = math.hypot(predicted[0] - observed[0], predicted[1] - observed[1])
        k = (name, pred_id)
        prev = self.err.get(k)
        self.err[k] = e if prev is None else (1 - EMA_ALPHA) * prev + EMA_ALPHA * e


class ReacquireController(USVController):
    def __init__(self):
        super().__init__()
        self._bank = _PredictorBank()
        self._stale_since = {}   # usv_name -> sim-t when its assigned target went stale
        self._pending = {}       # target_name -> (x, y, pred_id) chosen last stale step
        self.reacq_events = []   # diagnostics only

    def step(self, obs, tracks, legal, alloc_result, events, intent=None, mission=None):
        now = obs.now
        actions = super().step(obs, tracks, legal, alloc_result, events, intent, mission)
        # 1) feed predictor bank + score on fresh observations
        for tn, t in tracks.items():
            if t.is_visible(now) and t.has_position and t.last_position is not None:
                p = t.last_position
                if tn in self._pending:
                    self._bank.score(tn, self._pending[tn][2], (self._pending[tn][0], self._pending[tn][1]), (p[0], p[1]))
                    del self._pending[tn]
                self._bank.observe(tn, now, p[0], p[1])
        # 2) post-process ONLY assigned-and-stale USVs (else exact ACE behavior)
        for u in obs.usvs:
            if not u.get("is_alive") or not u.get("position"):
                continue
            name = u["name"]
            tname = self.targets.get(name)
            if not tname:
                self._stale_since.pop(name, None)
                continue
            t = tracks.get(tname)
            if t is None or not t.has_position or t.is_visible(now) or tname in _KILLED:
                self._stale_since.pop(name, None)
                continue
            # stale-but-present assigned target -> REACQUIRE window
            t0 = self._stale_since.setdefault(name, now)
            stale_time = now - t0
            unc = t.uncertainty(now) if hasattr(t, "uncertainty") else 0.0
            if stale_time > MAX_REACQUIRE_TIME or unc > U_MAX:
                continue  # EXPIRED -> keep parent (ACE) action already emitted
            px, py, pid = self._bank.predict(tname, now, t)
            if px is None:
                continue
            self._pending[tname] = (px, py, pid)
            self.reacq_events.append(("REACQUIRE", name, tname, round(stale_time, 1), pid))
            pos = (u["position"][0], u["position"][1])
            crs = bearing_to(pos, (px, py))
            act = (f"{name} 移动 target_speed={USV_SPEED:.1f} target_course={crs:.1f}", "move")
            actions = [a for a in actions if not (a[0].split(" ", 1)[0] == name and a[1] == "move")]
            actions.append(act)
        return actions


class TrackReacquireAgentMain(ExpandAgentMain):
    def __init__(self, use_uavs=True, max_steps=40000):
        super().__init__(use_uavs=use_uavs, max_steps=max_steps)
        self.usv_ctrl = ReacquireController()


if __name__ == "__main__":
    use_uavs = True
    for a in sys.argv[1:]:
        if a == "--no-uav":
            use_uavs = False
    TrackReacquireAgentMain(use_uavs=use_uavs).run()
