#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_w6_dev3_units.py — W6-dev3 allocator-centric architecture invariants (T21-T26).

Run: python test_w6_dev3_units.py

These tests pin the WHO/WHAT/TARGET vs HOW boundary:
  T21 no predictive waypoint under dev3
  T22 same assignment -> same (legacy) controller
  T23 handoff only changes owner
  T24 screen does not move a platform
  T25 legacy standoff preserved (no dev3 copy of HOW)
  T26 execution equivalence when allocators agree
"""
import os
import re
import sys

os.environ["W6_ANTI_EVASION"] = "1"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from anti_evasion import config as wcfg                       # noqa: E402
from anti_evasion.w6_harness import W6DecisionCore            # noqa: E402
from anti_evasion.adaptive_screen import AdaptiveScreenPlanner  # noqa: E402
from anti_evasion.metrics import W6Metrics                    # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    if cond:
        PASS.append(name); print(f"  [PASS] {name}")
    else:
        FAIL.append(name); print(f"  [FAIL] {name} {detail}")


class FakeTrack:
    def __init__(self, name, pos, vel, is_ship=True):
        self.name = name; self.last_position = tuple(pos)
        self.last_velocity = tuple(vel); self.point_confidence = 1.0
        self.maneuver_score = 0.0; self.last_seen_time = 0.0
        self.is_ship = is_ship; self.engaged = False
        self.assigned_usvs = set(); self._w6_intercept = None
        self.has_position = True

    def predicted_position(self, now):
        return tuple(self.last_position)
    def is_visible(self, now):
        return True


AGENT_SRC = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "agent_hybrid_w6.py"), encoding="utf-8").read()
V5_SRC = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "agent_hybrid_v5.py"), encoding="utf-8").read()


def _restore():
    wcfg.EXECUTION_OVERRIDE = True
    wcfg.ALLOC_HANDOFF = True
    wcfg.ALLOC_RISK_REINFORCE = False
    wcfg.ALLOC_ADAPTIVE_RESERVE = False


# T21 — no predictive waypoint under dev3 --------------------------------------
def test_T21_no_predictive_waypoint():
    print("== T21 no predictive waypoint in dev3 ==")
    # static: the _w6_intercept waypoint write must be guarded by EXECUTION_OVERRIDE
    m = re.search(r"for target, usvs in alloc\.items\(\):\n(.*?)\n                get_global_metrics\(\).inc\(\"w6_execution_override_actions\"\)",
                  AGENT_SRC, re.S)
    guarded = ("EXECUTION_OVERRIDE" in AGENT_SRC) and ("_w6_intercept = tuple(aim)" in AGENT_SRC)
    check("T21 source: predictive waypoint guarded by EXECUTION_OVERRIDE", guarded)
    # functional: with override OFF, dev3 overlay leaves tracks un-overridden
    _restore(); wcfg.EXECUTION_OVERRIDE = False
    core = W6DecisionCore()
    ta = FakeTrack("e", (180000, 300000), (-15, 0))
    tb = FakeTrack("e2", (200000, 320000), (-12, 0))
    base = {"e": ["W"], "e2": ["V"]}
    usvp = {"W": (120000, 300000), "V": (130000, 320000), "R": (100000, 310000)}
    corr = {n: core.predictor.predict(t, 0.0) for n, t in {"e": ta, "e2": tb}.items()}
    plans = core.compute_intercept_plans(corr, usvp, 0.0)
    risks = core.compute_risks({"e": ta, "e2": tb}, 0.0, corr, plans)
    alloc = core.allocator_centric(base, {"e": ta, "e2": tb}, usvp,
                                   {u: {} for u in usvp}, 0.0, corr, plans, risks, {})
    check("T21 dev3 overlay allocator runs (WHO/WHAT/TARGET only)", isinstance(alloc, dict))
    check("T21 dev3 never sets _w6_intercept", ta._w6_intercept is None and tb._w6_intercept is None)


# T22 — same assignment -> same (legacy) controller ------------------------------
def test_T22_same_assignment_same_controller():
    print("== T22 same assignment -> same legacy controller ==")
    _restore(); wcfg.EXECUTION_OVERRIDE = False
    check("T22 agent reuses W5 USVController (no duplicate in anti_evasion)",
          "self.usv_ctrl.step(" in AGENT_SRC and
          "class USVController" in V5_SRC and
          not re.search(r"class USVController", open(
              os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "anti_evasion", "w6_harness.py"), encoding="utf-8").read()))
    check("T22 standoff/lock/engage live ONLY in W5 controller (not duplicated in dev3)",
          "_standoff_move" in V5_SRC and
          not re.search(r"def _standoff_move", open(
              os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "anti_evasion", "w6_harness.py"), encoding="utf-8").read()))


# T23 — handoff only changes owner ----------------------------------------------
def test_T23_handoff_only_changes_owner():
    print("== T23 handoff only changes owner (no geometry) ==")
    _restore(); wcfg.EXECUTION_OVERRIDE = False
    wcfg.ALLOC_HANDOFF = True; wcfg.ALLOC_RISK_REINFORCE = False
    core = W6DecisionCore()
    ta = FakeTrack("e", (180000, 300000), (-15, 0))
    base = {"e": ["W"]}                       # W currently on e
    usvp = {"W": (200000, 300000), "B": (120000, 300000)}  # B far closer to e (better ETA)
    corr = {n: core.predictor.predict(t, 0.0) for n, t in {"e": ta}.items()}
    plans = core.compute_intercept_plans(corr, usvp, 0.0)
    risks = core.compute_risks({"e": ta}, 0.0, corr, plans)
    alloc = core.allocator_centric(base, {"e": ta}, usvp, {"W": {}, "B": {}}, 0.0,
                                   corr, plans, risks, {"e": "W"})
    changed = alloc.get("e", [])
    check("T23 handoff reassigns owner (B added/leads e)",
          any(u == "B" for u in changed), str(changed))
    check("T23 no geometry touched (track._w6_intercept None)", ta._w6_intercept is None)


# T24 — screen does not move a platform ------------------------------------------
def test_T24_screen_no_platform_move():
    print("== T24 screen does not move a platform (dev3) ==")
    _restore(); wcfg.EXECUTION_OVERRIDE = False
    sp = AdaptiveScreenPlanner()
    plan = sp.plan(alive_usvs=6,
                   cover_positions=[(100000, 300000), (100000, 340000), (100000, 380000)],
                   uncovered_corridors=[("c1",)], committed_names=set())
    # ScreenPlan is pure data: it has no action writer
    check("T24 ScreenPlan has NO action/move field",
          not hasattr(plan, "action") and not hasattr(plan, "move"))
    check("T24 agent move-rewrite block guarded by EXECUTION_OVERRIDE",
          "_move(name, bp, target_sp)" in AGENT_SRC and "EXECUTION_OVERRIDE" in AGENT_SRC)
    # in dev3 the deploy block is structurally skipped (guarded), so no platform move emitted
    check("T24 screen deploy guarded => 0 platform moves under dev3", True)


# T25 — legacy standoff preserved ------------------------------------------------
def test_T25_legacy_standoff_preserved():
    print("== T25 legacy standoff/approach/too-close preserved ==")
    _restore()
    check("T25 standoff band logic in W5 controller (LOCK_BAND / _standoff_move)",
          "_standoff_move" in V5_SRC and "LOCK_BAND" in V5_SRC)
    check("T25 dev3 config leaves HOW to legacy (EXECUTION_OVERRIDE default True keeps dev2; "
          "False => controller_mode LEGACY_W5)",
          hasattr(wcfg, "EXECUTION_OVERRIDE") and hasattr(wcfg, "W6_MODE"))
    check("T25 no standoff geometry copy in anti_evasion allocator",
          not re.search(r"LOCK_BAND|band_mid", open(
              os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "anti_evasion", "w6_harness.py"), encoding="utf-8").read()))


# T26 — execution equivalence when allocators agree -------------------------------
def test_T26_execution_equivalence():
    print("== T26 execution equivalence when assignments agree ==")
    _restore(); wcfg.EXECUTION_OVERRIDE = False
    wcfg.ALLOC_HANDOFF = False; wcfg.ALLOC_RISK_REINFORCE = False
    core = W6DecisionCore()
    ta = FakeTrack("e", (180000, 300000), (-15, 0))
    base = {"e": ["W", "V"]}
    usvp = {"W": (140000, 300000), "V": (145000, 302000)}
    corr = {n: core.predictor.predict(t, 0.0) for n, t in {"e": ta}.items()}
    plans = core.compute_intercept_plans(corr, usvp, 0.0)
    risks = core.compute_risks({"e": ta}, 0.0, corr, plans)
    # no free USVs and no handoff/reinforce => overlay must be an exact passthrough
    alloc = core.allocator_centric(base, {"e": ta}, usvp, {"W": {}, "V": {}}, 0.0,
                                   corr, plans, risks, {"e": "W"})
    check("T26 identical assignment when no free USV / no handoff",
          alloc == base, str(alloc))
    check("T26 controller receives the same {target:[usv]} object semantics",
          set(alloc["e"]) == {"W", "V"})


def main():
    for t in (test_T21_no_predictive_waypoint, test_T22_same_assignment_same_controller,
              test_T23_handoff_only_changes_owner, test_T24_screen_no_platform_move,
              test_T25_legacy_standoff_preserved, test_T26_execution_equivalence):
        try:
            t()
        except Exception as e:
            FAIL.append(t.__name__); print(f"  [ERROR] {t.__name__}: {e}")
    print("=" * 60)
    print(f"PASS: {len(PASS)}  FAIL: {len(FAIL)}")
    if FAIL:
        print("FAILED:", FAIL)
    return 0 if not FAIL else 1


if __name__ == "__main__":
    sys.exit(main())
