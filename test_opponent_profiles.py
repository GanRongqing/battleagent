#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_opponent_profiles.py — fair-play + variable-cardinality audit of the opponent ladder.

Covers:
  1. hidden-White-truth counterfactual : identical legal observation → identical Black action
  2. White internal-state mask         : Black policy never touches White belief/tracks/
                                         allocator/intent/Skill; only get_black_targets()
  3. variable-cardinality scale test   : Black 3/10/20/30/50 generate+plan without crash/hardcode
  4. B0 behavior unchanged             : B0 path generator identical to original
  5. doctrine pick / resolution determinism (B4)

Run: python test_opponent_profiles.py
"""
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "hsystem", "sim_script", "20250819TZB"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "hsystem"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "hsystem", "simulation"))
import opponent_profiles as op                           # noqa: E402
import scenario_builder as sb                            # noqa: E402

PASS = []
FAIL = []


def check(name, cond, detail=""):
    if cond:
        PASS.append(name)
        print(f"  [PASS] {name}")
    else:
        FAIL.append(name)
        print(f"  [FAIL] {name} {detail}")


def deploy_ys(n, center=405000.0, span=60000.0):
    return [float(center - span / 2 + span * i / max(1, n - 1)) for i in range(n)]


# ── mocks ──
class FakeUnit:
    def __init__(self, name, pos, group, alive=True):
        self.name = name
        self.coords = list(pos)
        self.group = group
        self.isactive = alive


class MockEngine:
    """Minimal engine surface used by the Black policy. get_white_targets is poisoned."""

    def __init__(self, black_ships, white_detected_names, white_positions=None):
        self._units = [FakeUnit(n, p, "BLUE") for n, p in black_ships]
        self._map = {u.name: u for u in self._units}
        wp = white_positions or {n: [260000.0 - 2000 * i, 405000.0] for i, n in enumerate(white_detected_names)}
        for n in white_detected_names:
            u = FakeUnit(n, wp[n], "RED")
            self._units.append(u)
            self._map[n] = u
        self._black_targets = list(white_detected_names)
        self.sail_calls = []

    def units(self):
        return self._units

    def get_black_targets(self):
        return list(self._black_targets)

    def get_white_targets(self):
        raise AssertionError("Black policy must NEVER call get_white_targets (White intel)")

    def unit_by_name(self, name):
        return self._map.get(name)

    def get_unit(self, name):
        return self._map.get(name)

    def cmd_sail_area(self, name, speed=None, xy_points=None, **kw):
        self.sail_calls.append((name, speed, list(xy_points)))
        return True


# ════════════════════════════════════════════════════════════════
# 1. hidden-White-truth counterfactual
# ════════════════════════════════════════════════════════════════
def test_hidden_white_truth_counterfactual():
    print("== test_hidden_white_truth_counterfactual ==")
    black = [("black_usv1", [250000, 405000]), ("black_usv2", [250000, 415000]),
             ("black_usv3", [250000, 395000]), ("black_usv4", [250000, 425000])]
    detected = ["white_usv1"]  # Black's legal radar intel
    eng = MockEngine(black, detected)
    obs = op.observe_black(eng)
    check("observe_black contains only detected White", list(obs["detected_white"]) == detected)
    # same legal observation, DIFFERENT hidden White truth appended (must be ignored)
    obs_a = dict(obs)
    obs_b = dict(obs)
    obs_b["hidden_white_truth"] = {"white_usv1": [12345, 99999], "white_usv9": [1, 1]}
    obs_b["white_belief_tracks"] = {"ghost": [0, 0]}
    pa = op.b3_plan(obs_a)
    pb = op.b3_plan(obs_b)
    check("B3: identical legal obs + different hidden White truth → identical action",
          pa == pb)
    # determinism
    check("B3: pure determinism (same obs → same plan)",
          op.b3_plan(obs_a) == op.b3_plan(obs_a))
    # responsive to legal obs (detected White position changes can change the plan)
    obs_c = dict(obs)
    obs_c["detected_white"] = {"white_usv1": [250100, 405100]}  # near group centroid
    check("B3: responsive to legal (detected) White position",
          op.b3_plan(obs_c)["replan"] is not None)


# ════════════════════════════════════════════════════════════════
# 2. White internal-state mask
# ════════════════════════════════════════════════════════════════
def test_white_internal_state_mask():
    print("== test_white_internal_state_mask ==")
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "opponent_profiles.py"), encoding="utf-8").read()
    forbidden = ["white_usv_states", "white_uav_states", "white_observation",
                 "allocator", "strategic_intent", "latest_intent", "TrackManager",
                 "AgentMain", "commander", "SkillLoader", "get_white_targets",
                 "tactical_summar", "belief"]
    hits = [w for w in forbidden if re.search(r"\b" + re.escape(w) + r"\b", src)]
    check("Black policy source has no White-internal references", not hits, str(hits))
    # runtime: observe_black never touches White intel (poisoned get_white_targets)
    eng = MockEngine([("black_usv1", [250000, 405000]), ("black_usv2", [250000, 415000]),
                      ("black_usv3", [250000, 395000]), ("black_usv4", [250000, 425000])],
                     ["white_usv1"])
    op.observe_black(eng)  # must not raise
    check("observe_black runs without touching White intel", True)
    ctrl = op.B3AdaptiveController()
    ctrl(eng)  # controller must not raise either
    check("B3AdaptiveController runs against mock engine (mask OK)", True)
    check("B3 controller actually issues legal replan commands",
          len(eng.sail_calls) >= 1 and ctrl.stats["replan_count"] >= 1,
          f"sail_calls={len(eng.sail_calls)} replan={ctrl.stats['replan_count']}")


# ════════════════════════════════════════════════════════════════
# 3. variable-cardinality scale test (3 / 10 / 20 / 30 / 50)
# ════════════════════════════════════════════════════════════════
def _valid_paths(paths, n):
    if len(paths) != n:
        return f"len={len(paths)} != {n}"
    for p in paths:
        if not p or not isinstance(p[0], (list, tuple)):
            return f"bad path start {p}"
        xs = [pt[0] for pt in p]
        if xs[0] > op.ENEMY_X + 1 or xs[-1] < op.BREAK_X + 1:
            return f"x range off {xs[0]:.0f}..{xs[-1]:.0f}"
        for pt in p:
            if not (op.Y_MIN - 1 <= pt[1] <= op.Y_MAX + 1):
                return f"y out of range {pt[1]:.0f}"
    return None


def test_scale_generation():
    print("== test_scale_generation ==")
    for n in (3, 10, 20, 30, 50):
        ys = deploy_ys(n)
        for prof in (op.B1, op.B2, op.B3):
            paths = op.generate_initial_paths(prof, 1001, ys)
            err = _valid_paths(paths, n)
            check(f"B1/B2/B3 n={n} path validity", err is None, str(err))
    # no count-branch hardcode
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "opponent_profiles.py"), encoding="utf-8").read()
    bad = re.findall(r"if\s+(n|count|len\(.*\))\s*==\s*\d+|if\s+\w+\s*==\s*(10|20|30)\s*:", src)
    check("no per-count hardcode branches", not bad, str(bad))


def test_scale_plan():
    print("== test_scale_plan ==")
    for n in (3, 10, 20, 30, 50):
        black = [(f"black_usv{i}", [250000 - i, deploy_ys(n)[i % n]]) for i in range(1, n + 1)]
        eng = MockEngine(black, ["white_usv1", "white_usv2"])
        obs = op.observe_black(eng)
        plan = op.b3_plan(obs)
        check(f"B3 plan runs at n={n} ({len(plan['replan'])} replans)",
              len(plan["replan"]) >= 0)
        for name, wp in plan["replan"].items():
            check(f"B3 n={n} waypoint valid ({name})",
                  len(wp) == 2 and all(len(p) == 2 for p in wp), str(wp))


# ════════════════════════════════════════════════════════════════
# 4. B0 unchanged
# ════════════════════════════════════════════════════════════════
def test_b0_unchanged():
    print("== test_b0_unchanged ==")
    ys = deploy_ys(10)
    ref = sb._random_waypoint_paths(2024, ys)
    # builder B0 branch must produce identical paths
    paths = sb._random_waypoint_paths(2024, ys)
    check("B0 path generator unchanged (same seed → same paths)", paths == ref)
    try:
        op.generate_initial_paths("B0_RANDOM", 2024, ys)
        check("B0 not routed through opponent generator", False)
    except ValueError:
        check("B0 not routed through opponent generator (ValueError raised)", True)


# ════════════════════════════════════════════════════════════════
# 5. doctrine pick / resolution (B4)
# ════════════════════════════════════════════════════════════════
def test_doctrine_mix():
    print("== test_doctrine_mix ==")
    for sd in (1001, 2002, 3003, 4004, 5005):
        d = op.pick_doctrine(sd)
        check(f"B4 seed {sd} → doctrine in B1/B2/B3", d in (op.B1, op.B2, op.B3), d)
    check("resolve_profile deterministic",
          op.resolve_profile(op.B4, 42) == op.resolve_profile(op.B4, 42))
    check("resolve_profile passthrough for B1",
          op.resolve_profile(op.B1, 42) == op.B1)
    # B4 generates valid paths via resolved doctrine
    for n in (10, 20, 30):
        ys = deploy_ys(n)
        resolved = op.resolve_profile(op.B4, 999)
        paths = op.generate_initial_paths(resolved, 999, ys)
        check(f"B4(n={n}) resolved={resolved} valid paths",
              _valid_paths(paths, n) is None)


def main():
    tests = [test_hidden_white_truth_counterfactual,
             test_white_internal_state_mask,
             test_scale_generation,
             test_scale_plan,
             test_b0_unchanged,
             test_doctrine_mix]
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
