#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""dev3/replay_audit/replay_analysis.py — offline same-state allocator replay.

Loads allocator_states.jsonl (legal belief snapshots from a LIVE FULL_DEV3 run). For each
state it recomputes, in strict cumulative order, the allocator output of:
  A W5_BASE, B +Prediction, C +Risk, D +Pursuit, E +Handoff, F +Reserve
on the SAME legal input (deep-copied), with NO simulator call. Then it aggregates:
activation, decision-change, score margin, handoff-gate, determinism, hidden-truth.

Variant semantics map onto allocator_centric's component gates:
  prediction alone never enters a decision pass (structural), risk gates reinforcement,
  pursuit changes reinforcement/handoff candidate ranking, handoff gates owner change,
  reserve caps how many free USVs may be pulled.
"""
import csv
import hashlib
import json
import math
import os
import random
import sys
import types

os.environ.setdefault("W6_ANTI_EVASION", "1")
os.environ.setdefault("W6_MODE", "dev3")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
OUT = os.path.dirname(os.path.abspath(__file__))

from agent_hybrid_v5 import EnemyTrack, ThreatAllocator, USVController  # noqa: E402
from anti_evasion import config as cfg                              # noqa: E402
from anti_evasion.w6_harness import W6DecisionCore                  # noqa: E402
from anti_evasion.handoff import HandoffEvaluator                   # noqa: E402
from anti_evasion.metrics import W6Metrics                          # noqa: E402
import types as _t

FIELDS = ["focus_level", "emergency_focus_level", "engagement_aggressiveness",
          "reserve_usvs", "reserve_ratio", "threat_bias", "priority_tracks",
          "overmatch_policy", "uncertainty_tolerance"]


def rebuild_track(s):
    t = EnemyTrack(s["name"], 0.0)
    t.last_position = tuple(s["position"]) if s["position"] else None
    t.last_velocity = tuple(s["velocity"]) if s["velocity"] else None
    t.last_seen_time = float(s["last_seen"])
    t.first_seen_time = 0.0
    t.confidence = s.get("confidence", 1.0)
    t.has_position = bool(s.get("has_position"))
    t.heading = s.get("heading")
    t.prev_heading = None
    t.turn_events = s.get("turn_events", 0)
    t.maneuver_score = s.get("maneuver_score", 0.0)
    t.point_confidence = s.get("point_confidence", 1.0)
    t.uncertainty_radius = s.get("uncertainty_radius", 4000.0)
    t.pred_errors = list(s.get("pred_errors", []))
    t.is_ship = bool(s.get("is_ship"))
    t.assigned_usvs = set(s.get("assigned_usvs", []))
    t.engaged = bool(s.get("engaged"))
    return t


def rebuild_intent(d):
    defs = {"focus_level": 2, "emergency_focus_level": 3, "engagement_aggressiveness": 0.5,
            "reserve_usvs": None, "reserve_ratio": 0.2, "threat_bias": "balanced",
            "priority_tracks": [], "overmatch_policy": "balanced", "uncertainty_tolerance": 0.35}
    ns = _t.SimpleNamespace()
    for k, dv in defs.items():
        v = d.get(k, dv)
        if k == "priority_tracks":
            v = list(v or [])
        if k == "reserve_usvs" and v is not None:
            v = int(v)
        setattr(ns, k, v)
    return ns


def sig(alloc):
    return tuple(sorted((tgt, tuple(sorted(usvs))) for tgt, usvs in alloc.items()))


def load_states(path):
    states = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        states.append(json.loads(line))
    return states


def build_inputs(state):
    tracks = {}
    for name, s in state["tracks"].items():
        tracks[name] = rebuild_track(s)
    usvs = [{"name": u["name"], "position": u.get("position"),
             "is_alive": bool(u.get("alive")), "is_locking": bool(u.get("is_locking")),
             "locking_unit": u.get("locking_unit"), "is_frozen": bool(u.get("is_frozen"))}
            for u in state["friendly_usvs"] if u.get("alive")]
    usv_map = {k: (v if v else None) for k, v in state["usv_map"].items()}
    now = float(state["sim_time"])
    intent = rebuild_intent(state.get("intent", {}))
    usv_positions = {u["name"]: tuple(u["position"][:2]) for u in usvs if u.get("position")}
    usv_states = {u["name"]: {"is_locking": bool(u.get("is_locking")),
                              "locking_unit": u.get("locking_unit"), "locked_since": None}
                  for u in state["friendly_usvs"]}
    return tracks, usvs, usv_map, now, intent, usv_positions, usv_states


class Gates:
    pass


def set_gates(**kw):
    for k in ("ISO_MODE", "ISO_PREDICTION", "ISO_RISK", "ISO_PURSUIT", "ISO_HANDOFF",
              "ISO_RESERVE"):
        setattr(cfg, k, kw.get(k, False))
    cfg.ALLOC_RISK_REINFORCE = kw.get("risk", False)
    cfg.ALLOC_HANDOFF = kw.get("handoff", False)
    cfg.ALLOC_ADAPTIVE_RESERVE = kw.get("reserve", False)


def run_w5(state):
    tracks, usvs, usv_map, now, intent, _, _ = build_inputs(state)
    alloc = ThreatAllocator().allocate_usvs(tracks, usvs, usv_map, now, intent=intent)
    return alloc


def run_w6(state, gates, core, metrics):
    tracks, usvs, usv_map, now, intent, usvp, usvs_ = build_inputs(state)
    base = {t: list(u) for t, u in state["base_alloc"].items()}
    feat = core.features(tracks, usvs, now, usvp, usvs_)
    core.metrics = metrics
    set_gates(**gates)
    alloc = core.allocator_centric(base, tracks, usvp, usvs_, now,
                                   feat["corridors"], feat["intercept_plans"],
                                   feat["risks"], {t: (usv_map.get(t) or None)
                                                   for t in base})
    return alloc


def main():
    path = os.path.join(OUT, "allocator_states.jsonl")
    states = load_states(path)
    print("states:", len(states))
    variants = ["A_W5", "B_Pred", "C_Risk", "D_Pursuit", "E_Handoff", "F_Reserve"]
    gates_of = {"B_Pred": dict(pred=True), "C_Risk": dict(pred=True, risk=True),
                "D_Pursuit": dict(pred=True, risk=True, pursuit=True),
                "E_Handoff": dict(pred=True, risk=True, pursuit=True, handoff=True),
                "F_Reserve": dict(pred=True, risk=True, pursuit=True, handoff=True,
                                  reserve=True)}
    # replay sequentially per episode (cooldown/order preserved)
    by_ep = {}
    for i, s in enumerate(states):
        by_ep.setdefault(s["episode"], []).append(s)
    rows = []
    for ep, epstates in by_ep.items():
        for v in variants:
            core = W6DecisionCore()
            metrics = W6Metrics()
            prev_sig = None
            for s in epstates:
                try:
                    if v == "A_W5":
                        a = run_w5(s)
                    else:
                        a = run_w6(s, gates_of[v], core, metrics)
                except Exception as e:
                    rows.append([ep, s["decision_index"], v, s["sim_time"], "ERROR", str(e)[:80]])
                    continue
                sg = sig(a)
                rows.append([ep, s["decision_index"], v, s["sim_time"], sg])
    # save replay results
    rp = os.path.join(OUT, "allocator_replay_results.csv")
    with open(rp, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["episode", "decision_index", "variant", "sim_time", "signature", "note"])
        for r in rows:
            sg = r[4]
            if isinstance(sg, str):
                w.writerow(r[:5] + [r[5] if len(r) > 5 else ""])
            else:
                h = hashlib.sha256(repr(sg).encode()).hexdigest()[:16]
                w.writerow([r[0], r[1], r[2], r[3], h, ""])
    print("replay rows:", len(rows))
    print("wrote", rp)


if __name__ == "__main__":
    sys.exit(main())
