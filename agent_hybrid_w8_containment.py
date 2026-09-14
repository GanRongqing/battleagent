#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""agent_hybrid_w8_containment.py — white-auto-0001-v1 (anti-leak containment).

Minimal overlay on frozen W5 (agent_hybrid_v5.py, immutable). Only the ALLOCATOR
(WHO is assigned) is changed, via ContainmentAllocator(ThreatAllocator). The
execution HOW (USVController / ActionSafety / UAVManager) is untouched.

Mechanisms (Phase-1, evidence-driven; see ANTI_LEAK_DESIGN.md):
  M1 CROSSING-RISK ESTIMATOR : legal track belief -> crossing ETA to BREAK_X.
  M2 BOUNDARY COVERAGE CHECK  : is there an effective blocker (between target and
                                boundary, or intercept-feasible before ETA)?
  M3 MINIMAL CONTAINMENT      : only when risk>=HIGH and no blocker, assign ONE
                                blocker (free first, then bounded preemption).

Outside the containment trigger the allocator returns W5's assignment unchanged.
All state comes from legal White tracks (beliefs); no hidden truth is used.
"""
import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agent_hybrid_v5 as w5  # noqa: E402

BREAK_X = 50000.0
ETA_CRITICAL = 3000.0
ETA_HIGH = 6000.0
ETA_MEDIUM = 10000.0
CONTAINMENT_TTL = 900.0          # sim-seconds commitment (hysteresis)
INTERCEPT_SPEED = 15.0           # nominal White USV closing speed for feasibility
BLOCKER_X_MARGIN = 5000.0        # blocker west of target counts as boundary-side
W8_EVENT_LOG = os.environ.get("W8_EVENT_LOG", "/tmp/opencode/w8_containment_events.json")


def _alive(u):
    return u.get("is_alive", True) and u.get("position")


class ContainmentAllocator(w5.ThreatAllocator):
    """W5 ThreatAllocator + minimal boundary-containment overlay."""

    def __init__(self):
        super().__init__()
        self._contained = {}          # target -> release_sim_time
        self._blocker_of = {}         # target -> usv
        self._audit_enabled = os.environ.get("W8_AUDIT_LOG")
        self._audit_records = []
        self._audit_step = 0
        self.stats = {"allocate_calls": 0, "risk_evaluated": 0, "high_risk_seen": 0,
                      "critical_risk_seen": 0, "containment_triggered": 0,
                      "preemptions": 0, "releases": 0, "blocker_demand_peak": 0,
                      "false_trigger_unknown": 0, "unblocked_high_risk_evals": 0,
                      "unblocked_critical_risk_evals": 0}

    # ── M1: legal crossing estimator ──
    def crossing_eta(self, t, now):
        pos = t.predicted_position(now) if hasattr(t, "predicted_position") else None
        if pos is None:
            pos = getattr(t, "last_position", None)
        vel = getattr(t, "last_velocity", None)
        if pos is None or vel is None:
            return None, None
        vx = vel[0]
        if vx >= -0.05:               # not closing on the boundary
            return None, pos
        return max(0.0, (pos[0] - BREAK_X) / (-vx)), pos

    def risk_level(self, eta, t):
        if eta is None:
            return "UNKNOWN"
        if eta <= ETA_CRITICAL:
            return "CRITICAL"
        if eta <= ETA_HIGH:
            return "HIGH"
        if eta <= ETA_MEDIUM:
            return "MEDIUM"
        return "LOW"

    # ── M2: effective blocker check (legal geometry) ──
    def effective_blocker(self, tname, t, tpos, eta, result, usv_pos, usv_map):
        names = list(result.get(tname, []))
        names += [u for u, trg in usv_map.items() if trg == tname]
        for uname in names:
            p = usv_pos.get(uname)
            if not p:
                continue
            if p[0] <= tpos[0] + BLOCKER_X_MARGIN:      # boundary-side of target
                return uname
            if eta is not None and math.hypot(p[0] - tpos[0], p[1] - tpos[1]) / INTERCEPT_SPEED <= eta:
                return uname
        return None

    def allocate_usvs(self, tracks, usvs, usv_map, now, intent=None,
                      return_margin=False, candidates=None):
        out = super().allocate_usvs(tracks, usvs, usv_map, now, intent=intent,
                                    return_margin=True, candidates=candidates)
        result, margin = out if isinstance(out, tuple) else (out, None)
        self.stats["allocate_calls"] += 1
        usv_pos = {u["name"]: (u["position"][0], u["position"][1])
                   for u in usvs if _alive(u)}
        # release expired / resolved containment
        for tname in list(self._contained):
            rel = self._contained[tname]
            t = tracks.get(tname)
            if now >= rel or t is None or not getattr(t, "has_position", False):
                self._contained.pop(tname, None)
                self._blocker_of.pop(tname, None)
                self.stats["releases"] += 1

        # evaluate risk
        risk_targets = []
        for tname, t in tracks.items():
            if not getattr(t, "is_ship", False) or not getattr(t, "has_position", False):
                continue
            if tname in w5._KILLED:
                continue
            eta, tpos = self.crossing_eta(t, now)
            lvl = self.risk_level(eta, t)
            self.stats["risk_evaluated"] += 1
            if lvl in ("HIGH", "CRITICAL"):
                self.stats["high_risk_seen"] += 1
                if lvl == "CRITICAL":
                    self.stats["critical_risk_seen"] += 1
                blocker = self.effective_blocker(tname, t, tpos, eta, result, usv_pos, usv_map)
                if blocker is None:
                    if lvl == "CRITICAL":
                        self.stats["unblocked_critical_risk_evals"] += 1
                    else:
                        self.stats["unblocked_high_risk_evals"] += 1
                    risk_targets.append((eta if eta is not None else 1e9, tname, tpos, lvl))

        risk_targets.sort()
        new_demand = 0
        selected = {}
        for _, tname, tpos, lvl in risk_targets:
            if tname in self._contained:
                continue
            blocker = self._pick_blocker(tname, tpos, result, usvs, usv_pos, tracks, usv_map)
            if blocker is None:
                continue
            result.setdefault(tname, []).append(blocker)
            self._contained[tname] = now + CONTAINMENT_TTL
            self._blocker_of[tname] = blocker
            self.stats["containment_triggered"] += 1
            new_demand += 1
            selected[tname] = {"blocker": blocker, "risk": lvl}
        self.stats["blocker_demand_peak"] = max(self.stats["blocker_demand_peak"], len(self._contained))
        if self._audit_enabled:
            self._audit_step += 1
            self._audit_records.append({
                "step": self._audit_step, "sim_time": round(now, 1),
                "unblocked_high": [{"track": tn, "eta": round(e, 1), "risk": lv}
                                   for e, tn, _, lv in risk_targets],
                "selected": selected,
                "contained_active": len(self._contained),
                "effective_blockers": sum(1 for tn in self._contained)})
            if len(self._audit_records) > 5000:
                self._audit_records = self._audit_records[-5000:]
        return (result, margin) if return_margin else result

    def _pick_blocker(self, tname, tpos, result, usvs, usv_pos, tracks, usv_map):
        assigned = {u for lst in result.values() for u in lst}
        free = [u["name"] for u in usvs if _alive(u) and u["name"] not in assigned
                and usv_map.get(u["name"]) is None]
        if free:
            return min(free, key=lambda n: math.hypot(usv_pos[n][0] - tpos[0], usv_pos[n][1] - tpos[1]))
        # bounded preemption: from a target (other than the risk target) that already
        # has >=2 assigned USVs (W5 current assignments via usv_map + this-step result).
        owners = {}
        for uname, trg in usv_map.items():
            if trg:
                owners.setdefault(trg, []).append(uname)
        for trg, lst in result.items():
            owners.setdefault(trg, []).extend(lst)
        best = None
        for other, lst in owners.items():
            if other == tname or len(lst) < 2:
                continue
            for uname in lst:
                if uname not in usv_pos:
                    continue
                d = math.hypot(usv_pos[uname][0] - tpos[0], usv_pos[uname][1] - tpos[1])
                if best is None or d < best[0]:
                    best = (d, other, uname)
        if best is None:
            return None
        _, other, uname = best
        if other in result and uname in result[other]:
            result[other].remove(uname)
        self.stats["preemptions"] += 1
        return uname

    def write_stats(self):
        try:
            data = dict(self.stats)
            data["contained_now"] = len(self._contained)
            with open(W8_EVENT_LOG, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception:
            pass
        if self._audit_enabled:
            try:
                with open(self._audit_enabled, "w", encoding="utf-8") as f:
                    for rec in self._audit_records:
                        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            except Exception:
                pass


class ContainmentAgent(w5.AgentMain):
    def __init__(self, use_uavs=True, max_steps=40000):
        super().__init__(use_uavs=use_uavs, max_steps=max_steps)
        self.allocator = ContainmentAllocator()
        try:
            self.summarizer.allocator = self.allocator
        except Exception:
            pass

    def run(self):
        try:
            super().run()
        finally:
            self.allocator.write_stats()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uavs", action="store_true", default=True)
    ap.add_argument("--no-uav", dest="uavs", action="store_false")
    ap.add_argument("--max-steps", type=int, default=40000)
    a = ap.parse_args()
    ContainmentAgent(use_uavs=a.uavs, max_steps=a.max_steps).run()


if __name__ == "__main__":
    main()
