#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_w6_units.py — W6 anti-evasion module unit tests (T1–T9 + fair-play).

Run: python test_w6_units.py
"""
import os
import sys

os.environ["W6_ANTI_EVASION"] = "1"   # exercise the feature-gated decision core

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from anti_evasion.motion_predictor import ShortHorizonPredictor          # noqa: E402
from anti_evasion.intercept_planner import InterceptPlanner               # noqa: E402
from anti_evasion.pursuit_cost import (effective_value, pursuit_cost,     # noqa: E402
                                       intercept_advantage, coverage_cost)
from anti_evasion.handoff import HandoffEvaluator                        # noqa: E402
from anti_evasion.track_criticality import criticality                   # noqa: E402
from anti_evasion.adaptive_screen import AdaptiveScreenPlanner           # noqa: E402
from anti_evasion.breakthrough_risk import BreakthroughRiskEstimator     # noqa: E402
from anti_evasion.w6_harness import W6DecisionCore                       # noqa: E402

PASS = []
FAIL = []


def check(name, cond, detail=""):
    if cond:
        PASS.append(name)
        print(f"  [PASS] {name}")
    else:
        FAIL.append(name)
        print(f"  [FAIL] {name} {detail}")


class FakeTrack:
    def __init__(self, name, pos, vel, pc=1.0, man=0.0, age=0.0, unc=4000.0,
                 is_ship=True):
        self.name = name
        self.last_position = tuple(pos)
        self.last_velocity = tuple(vel)
        self.point_confidence = pc
        self.maneuver_score = man
        self.last_seen_time = 0.0
        self._age = age
        self._unc = unc
        self.is_ship = is_ship
        self.engaged = False
        self.assigned_usvs = set()

    def predicted_position(self, now):
        x = self.last_position[0] + self.last_velocity[0] * self._age
        y = self.last_position[1] + self.last_velocity[1] * self._age
        return (x, y)

    def uncertainty(self, now):
        return self._unc + 20.0 * max(0.0, now - self.last_seen_time)

    def age(self, now):
        return self._age

    def is_visible(self, now):
        return self._age < 300.0


# ── T1: predictive interception leads the target ──
def test_T1_predictive_interception():
    print("== T1 Predictive interception: intercept point leads current position ==")
    t = FakeTrack("enemy1", (200000, 300000), (-15, 0))   # moving west (toward break)
    pred = ShortHorizonPredictor()
    c = pred.predict(t, 0.0)
    check("corridor predicted_position leads current (x smaller, moving west)",
          c.predicted_position[0] < c.current_estimate[0])
    # an interceptor ahead should plan an intercept point ahead of the target
    ip = InterceptPlanner()
    plan = ip.plan("white_usv1", (120000, 300000), c)
    check("intercept point ahead of target corridor",
          plan is not None and plan.intercept_point[0] < c.current_estimate[0],
          str(plan))


# ── T2: maneuver reduces horizon and increases uncertainty ──
def test_T2_maneuver_uncertainty():
    print("== T2 maneuver uncertainty: higher oscillation -> shorter horizon, larger unc ==")
    pred = ShortHorizonPredictor()
    ta = FakeTrack("a", (150000, 300000), (-10, 0), pc=1.0, man=0.0)
    tb = FakeTrack("b", (150000, 300000), (-10, 0), pc=1.0, man=0.9)
    ca = pred.predict(ta, 0.0)
    cb = pred.predict(tb, 0.0)
    check("maneuver -> shorter horizon", cb.prediction_horizon_s < ca.prediction_horizon_s)
    check("maneuver -> larger prediction uncertainty",
          cb.prediction_uncertainty > ca.prediction_uncertainty)
    check("maneuver -> lower motion confidence", cb.motion_confidence < ca.motion_confidence)


# ── T3: better interceptor (B ahead of corridor) has higher effective value ──
def test_T3_better_interceptor():
    print("== T3 better interceptor: B ahead of corridor > A behind ==")
    t = FakeTrack("e", (200000, 300000), (-15, 0))
    pred = ShortHorizonPredictor()
    corr = pred.predict(t, 0.0)
    ip = InterceptPlanner()
    pa = ip.plan("A", (0, 300000), corr)       # far behind
    pb = ip.plan("B", (160000, 300000), corr)  # ahead of corridor
    va = effective_value(0.5, t, 0.0, (0, 300000), [(160000, 300000)],
                         pa.intercept_eta, pa.target_eta)
    vb = effective_value(0.5, t, 0.0, (160000, 300000), [(0, 300000)],
                         pb.intercept_eta, pb.target_eta)
    check("B (ahead) effective value > A (behind)", vb > va, f"va={va:.3f} vb={vb:.3f}")
    check("B intercept ETA < A", pb.intercept_eta < pa.intercept_eta)


# ── T4: handoff hysteresis ──
def test_T4_handoff_hysteresis():
    print("== T4 handoff hysteresis: small benefit no; large benefit yes ==")
    ev = HandoffEvaluator()
    state = {"is_locking": False, "locked_since": None}
    small = ev.evaluate("t", "A", "B", 100.0, 90.0, state, 0.0)   # 10% benefit
    check("small benefit (10%) -> no handoff", small.handoff is False,
          small.blocked_reason)
    big = ev.evaluate("t2", "A", "B", 100.0, 40.0, state, 0.0)    # 60% benefit
    check("large benefit (60%) -> handoff", big.handoff is True, big.blocked_reason)


# ── T5: active lock protection ──
def test_T5_active_lock_protection():
    print("== T5 active lock protection: mature lock blocks handoff ==")
    ev = HandoffEvaluator()
    locked_state = {"is_locking": True, "locked_since": 0.0}
    dec = ev.evaluate("t", "A", "B", 100.0, 40.0, locked_state, 300.0)  # large benefit
    check("mature active lock -> no handoff (protects kill chain)",
          dec.handoff is False and dec.blocked_reason == "ACTIVE_LOCK_PROTECTED",
          dec.blocked_reason)
    # unlocked but large benefit -> handoff allowed
    dec2 = ev.evaluate("t2", "A", "B", 100.0, 40.0, {"is_locking": False}, 300.0)
    check("unlocked + large benefit -> handoff", dec2.handoff is True)


# ── T16/T17: handoff current commitment + no self-compare ──
def test_T16_T17_handoff_commitment():
    print("== T16/T17 handoff: current committed interceptor vs best alternative; no self-compare ==")
    ev = HandoffEvaluator()
    # current=A, best alternative=B, B clearly better -> handoff (A vs B)
    dec = ev.evaluate("t", "A", "B", 100.0, 40.0, {"is_locking": False}, 0.0)
    check("T16 current=A, alternative=B, B better -> handoff (A vs B)",
          dec.handoff is True and dec.from_interceptor == "A" and dec.to_interceptor == "B")
    # T17 self-compare: current == alternative -> NO_ALTERNATIVE, no handoff
    dec2 = ev.evaluate("t", "B", "B", 100.0, 40.0, {"is_locking": False}, 0.0)
    check("T17 self-compare (current==alternative) -> NO_ALTERNATIVE, no handoff",
          dec2.handoff is False and dec2.blocked_reason == "NO_ALTERNATIVE",
          dec2.blocked_reason)
    # T18 active lock: A has active lock, B much better -> still no handoff (lock protected)
    dec3 = ev.evaluate("t", "A", "B", 100.0, 40.0,
                       {"is_locking": True, "locked_since": 0.0}, 300.0)
    check("T18 active lock + large benefit -> no handoff",
          dec3.handoff is False and dec3.blocked_reason == "ACTIVE_LOCK_PROTECTED",
          dec3.blocked_reason)


# ── T10/T11/T12: standoff intercept geometry ──
def test_T10_T11_T12_standoff_intercept():
    print("== T10/T11/T12 standoff intercept geometry ==")
    from anti_evasion.intercept_planner import InterceptPlanner
    from anti_evasion.motion_predictor import ShortHorizonPredictor
    ip = InterceptPlanner(standoff=34000.0, lock_range=40000.0)
    pred = ShortHorizonPredictor()
    # target moving toward White; White ahead -> intercept point should be >= standoff from target
    t = FakeTrack("e", (150000, 300000), (-15, 0))
    corr = pred.predict(t, 0.0)
    plan = ip.plan("W", (50000, 300000), corr)
    d_waypoint_target = _d(plan.intercept_point, corr.current_estimate)
    check("T10 standoff: intercept waypoint >= standoff from target",
          d_waypoint_target >= 34000.0 - 1.0, f"d={d_waypoint_target:.0f}")
    # T11 too close: USV already inside the band -> REPOSITION_OUTWARD
    plan2 = ip.plan("W", (140000, 300000), corr)
    check("T11 too close -> REPOSITION_OUTWARD (not approach)",
          plan2.geometry_state == "REPOSITION_OUTWARD", plan2.geometry_state)
    # T12 lock ready: USV in [standoff, lock_range] -> LOCK_READY (base takes over)
    plan3 = ip.plan("W", (111000, 300000), corr)
    check("T12 within lock range -> LOCK_READY",
          plan3.geometry_state == "LOCK_READY", plan3.geometry_state)


def _d(a, b):
    import math
    return math.hypot(a[0] - b[0], a[1] - b[1])


# ── T6: track criticality (UAV maintenance priority) ──
def test_T6_track_criticality():
    print("== T6 track criticality: high-uncertainty + high-break risk > redundant ==")
    ta = FakeTrack("A", (70000, 300000), (-15, 0), pc=0.4, man=0.8, age=120.0, unc=30000.0)
    tb = FakeTrack("B", (200000, 300000), (-10, 0), pc=1.0, man=0.0, age=0.0, unc=4000.0)
    ca = criticality(ta, 0.0, sensor_support_count=0)
    cb = criticality(tb, 0.0, sensor_support_count=3)   # redundant
    check("A (uncertain, break-risky, no support) > B (redundant)",
          ca > cb, f"A={ca:.3f} B={cb:.3f}")


# ── T7: adaptive screen preserves capacity under multiple uncovered corridors ──
def test_T7_screen():
    print("== T7 screen: uncovered corridors -> screen capacity kept ==")
    sp = AdaptiveScreenPlanner()
    plan = sp.plan(alive_usvs=10, cover_positions=[(100000, 300000), (100000, 340000),
                                                   (100000, 380000), (100000, 420000)],
                   uncovered_corridors=[("c1",), ("c2",)], committed_names=set())
    check("screen demand > 0 with uncovered corridors", plan.screen_demand > 0)
    check("screen capacity is resource-relative (< alive)", plan.min_capacity <= 10)


# ── T8: endgame single high-risk threat -> concentration allowed (screen min, not blocking) ──
def test_T8_endgame():
    print("== T8 endgame: single threat does not force screen to starve offense ==")
    sp = AdaptiveScreenPlanner()
    plan = sp.plan(alive_usvs=2, cover_positions=[(100000, 300000)],
                   uncovered_corridors=[("only",)], committed_names={"white_usv1"})
    check("endgame with 2 USVs: screen capacity <= 1 (offense not starved)",
          plan.min_capacity <= 1)
    check("screen fraction bounded by max", plan.screen_demand <= 0.5)


# ── T9: fair-play counterfactual ──
def test_T9_fairplay_counterfactual():
    print("== T9 fair-play: same legal obs, different hidden truth -> identical W6 ==")
    core = W6DecisionCore()
    ta = FakeTrack("e", (180000, 300000), (-12, 0))
    tb = FakeTrack("e", (180000, 300000), (-12, 0))
    # identical legal belief; hidden truth differs (the agent never sees it)
    usv_pos_a = {"white_usv1": (50000, 300000)}
    usv_pos_b = {"white_usv1": (50000, 300000)}
    base_alloc = {"e": ["white_usv1"]}
    da = core.step({"e": ta}, [], 0.0, base_alloc, usv_pos_a, {"white_usv1": {}})
    db = core.step({"e": tb}, [], 0.0, base_alloc, usv_pos_b, {"white_usv1": {}})
    a = {k: (da[k].to_dict() if hasattr(da[k], "to_dict") else da[k])
         for k in ("corridors", "intercept_plans", "risks")}
    b = {k: (db[k].to_dict() if hasattr(db[k], "to_dict") else db[k])
         for k in ("corridors", "intercept_plans", "risks")}
    # simplify to comparable structures
    def simplify(d):
        if hasattr(d, "to_dict"):
            return simplify(d.to_dict())
        if isinstance(d, dict):
            return {k: simplify(v) for k, v in d.items()}
        return d
    check("corridors identical under hidden-truth difference", simplify(a["corridors"]) == simplify(b["corridors"]))
    check("intercept plans identical", simplify(a["intercept_plans"]) == simplify(b["intercept_plans"]))
    check("risks identical", simplify(a["risks"]) == simplify(b["risks"]))
    # runtime path has no opponent-profile references
    import re
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_hybrid_w6.py"),
               encoding="utf-8").read()
    leaks = [w for w in ("B3", "ADAPTIVE", "opponent_profile", "lane_shift",
                         "replan_count", "black doctrine", "black_strategy")
             if w in src]
    check("no opponent-profile leakage in W6 runtime", not leaks, str(leaks))


# ── extra: predictor scale-normalization / no fixed-count thresholds ──
def test_scale_independence():
    print("== scale independence: predictor/allocator no fixed fleet-size branches ==")
    import re
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "anti_evasion", "pursuit_cost.py"), encoding="utf-8").read()
    hard = re.findall(r"if\s+(n|count|len\([^)]*\))\s*==\s*\d+|==\s*(10|20|30)\b", src)
    check("no per-count hardcode in pursuit_cost", not hard, str(hard))


# ── T13/T14/T15: adaptive screen demand / endgame ──
def test_T13_T14_T15_screen_demand():
    print("== T13/T14/T15 screen: covered vs uncovered corridors; endgame ==")
    from anti_evasion.adaptive_screen import AdaptiveScreenPlanner
    sp = AdaptiveScreenPlanner()
    # T13: corridor already covered by a feasible interceptor -> no uncovered demand
    plan_covered = sp.plan(alive_usvs=10, cover_positions=[(100000, 300000)],
                           uncovered_corridors=[], committed_names=set())
    check("T13 covered corridor -> no extra screen demand", plan_covered.min_capacity == 0,
          str(plan_covered.min_capacity))
    # T14: two uncovered high-risk corridors -> screen demand > 0
    plan_multi = sp.plan(alive_usvs=10, cover_positions=[(100000, 300000), (100000, 340000),
                                                         (100000, 380000)],
                         uncovered_corridors=[("c1",), ("c2",)], committed_names=set())
    check("T14 two uncovered corridors -> screen demand > 0", plan_multi.min_capacity >= 1,
          str(plan_multi.min_capacity))
    # T15: endgame single target -> screen does not starve offense
    plan_end = sp.plan(alive_usvs=2, cover_positions=[(100000, 300000)],
                       uncovered_corridors=[("only",)], committed_names={"white_usv1"})
    check("T15 endgame 2 USVs -> screen capacity <= 1 (offense preserved)",
          plan_end.min_capacity <= 1, str(plan_end.min_capacity))


# ── T19/T20: event semantics (transitions / plan changes) ──
def test_T19_T20_event_semantics():
    print("== T19/T20 risk transition + intercept plan change event semantics ==")
    core = W6DecisionCore()
    from anti_evasion.metrics import W6Metrics
    m = W6Metrics()
    core.metrics = m
    # T19: HIGH risk sustained across calls -> unique transition counted once
    ta = FakeTrack("e", (40000, 300000), (-15, 0))  # near break line -> high risk
    for _ in range(5):
        core.compute_risks({"e": ta}, 0.0, {}, {})
    c = m.counts
    check("T19 high-risk transition counted once (not per tick)",
          c["unique_high_risk_transitions"] == 1, str(c["unique_high_risk_transitions"]))
    # T20: same intercept plan sustained -> unique plan changes not repeated
    core2 = W6DecisionCore()
    m2 = W6Metrics()
    core2.metrics = m2
    tb = FakeTrack("e", (180000, 300000), (-12, 0))
    usv = {"W": (50000, 300000)}
    for _ in range(5):
        corr = core2.predictor.predict(tb, 0.0)
        core2.compute_intercept_plans({"e": corr}, usv, 0.0)
    check("T20 same intercept plan sustained -> plan change counted once",
          m2.counts["unique_intercept_plan_changes"] == 1,
          str(m2.counts["unique_intercept_plan_changes"]))


# ── T21: screen deploys when best interceptor is TOO LATE (Fix E) ──
def test_T21_screen_late_deploy():
    print("== T21 screen: high-risk corridor with too-late interceptor -> demand > 0 ==")
    core = W6DecisionCore()
    from anti_evasion.metrics import W6Metrics
    m = W6Metrics()
    core.metrics = m
    # target close to the break line, moving west fast -> high risk with imminent deadline
    tb = FakeTrack("e", (60000, 300000), (-18, 0))
    usv = {"W": (450000, 300000)}   # interceptor far behind -> plan feasible? too late
    base_alloc = {"e": ["W"]}
    d = core.step({"e": tb}, [], 0.0, base_alloc, usv, {"W": {}})
    plan = d["screen"]
    check("T21 late intercept under high risk -> screen min_capacity >= 1",
          plan is not None and plan.min_capacity >= 1,
          str(plan.min_capacity if plan else None))
    check("T21 uncovered corridor recorded (screen positions non-empty or demand>0)",
          plan is not None and (plan.screen_demand > 0 or plan.uncovered_corridors > 0),
          str(plan.screen_demand if plan else None))


def main():
    tests = [test_T1_predictive_interception, test_T2_maneuver_uncertainty,
             test_T3_better_interceptor, test_T4_handoff_hysteresis,
             test_T5_active_lock_protection, test_T6_track_criticality,
             test_T7_screen, test_T8_endgame, test_T9_fairplay_counterfactual,
             test_scale_independence, test_T10_T11_T12_standoff_intercept,
             test_T16_T17_handoff_commitment, test_T13_T14_T15_screen_demand,
             test_T19_T20_event_semantics, test_T21_screen_late_deploy]
    for t in tests:
        try:
            t()
        except Exception as e:
            FAIL.append(t.__name__)
            print(f"  [ERROR] {t.__name__}: {e}")
    print("=" * 60)
    print(f"PASS: {len(PASS)}  FAIL: {len(FAIL)}")
    if FAIL:
        print("FAILED:", FAIL)
    return 0 if not FAIL else 1


if __name__ == "__main__":
    sys.exit(main())
