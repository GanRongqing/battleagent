#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_b0_v2.py — black-b0-v2 variable-speed tests (B0V2-T1..T10)."""
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "hsystem"))
import opponent_b0_v2 as b0v2  # noqa: E402

PASS, FAIL = [], []


def check(name, c, d=""):
    (PASS if c else FAIL).append(name)
    print(f"  [{'PASS' if c else 'FAIL'}] {name} {d}")


def _sb():
    spec = importlib.util.spec_from_file_location(
        "scenario_builder", os.path.join(ROOT, "hsystem", "sim_script",
                                         "20250819TZB", "scenario_builder.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    sb = _sb()
    ys = sb._deploy_ys(20, "fixed_frontage")

    # B0V2-T1 same seed -> same speed
    check("B0V2-T1 same seed -> same sampled speed",
          b0v2.sample_speed(9001) == b0v2.sample_speed(9001))

    # B0V2-T2 different seeds -> speed can differ
    vals = [b0v2.sample_speed(s) for s in range(9001, 9010)]
    check("B0V2-T2 different seeds -> speed can differ", len(set(vals)) > 1, f"uniq={len(set(vals))}")

    # B0V2-T3 within legal/operational range
    allv = [b0v2.sample_speed(s) for s in range(9001, 9091)]
    check("B0V2-T3 sampled speed within [5,10]",
          all(b0v2.V_MIN_OPERATIONAL <= v <= b0v2.V_MAX_OPERATIONAL for v in allv),
          f"min={min(allv)} max={max(allv)}")

    # B0V2-T4 speed RNG does not consume waypoint RNG
    p1 = sb._random_waypoint_paths(9001, ys)
    _ = b0v2.sample_speed(9001)
    p2 = sb._random_waypoint_paths(9001, ys)
    check("B0V2-T4 speed RNG isolated from waypoint RNG", p1 == p2)

    # B0V2-T5 B0 waypoint logic unchanged (v2 uses the same generator)
    src = open(os.path.join(ROOT, "opponent_b0_v2.py"), encoding="utf-8").read()
    check("B0V2-T5 waypoint logic unchanged (no path function in v2 module)",
          "_random_waypoint_paths" not in src and "def " in src and "sample_speed" in src)

    # B0V2-T6 no adaptive replanning
    check("B0V2-T6 no adaptive replanning introduced",
          "replan" not in src.lower() and "controller" not in src.lower())

    # B0V2-T7 no coordination
    check("B0V2-T7 no coordination introduced",
          not any(t in src.lower() for t in ("group(", "lane", "synchron", "assign", "formation")))

    # B0V2-T8 no hidden White truth
    check("B0V2-T8 no hidden White truth used",
          not any(t in src for t in ("get_white_targets", "ground_truth", "hidden", "white_")))

    # B0V2-T9 requested policy reaches simulator (integration tokens present)
    sb_src = open(os.path.join(ROOT, "hsystem", "sim_script", "20250819TZB",
                               "scenario_builder.py"), encoding="utf-8").read()
    check("B0V2-T9 profile token + effective id + meta wired",
          "B0_V2_VARIABLE_SPEED" in sb_src and "effective=black-b0-v2" in sb_src and
          "b0v2_meta.json" in sb_src and "speed=_black_speed" in sb_src)

    # B0V2-T10 commanded speed varies across pilot seeds (actual verified in pilot)
    check("B0V2-T10 commanded speed varies across seeds",
          len({b0v2.sample_speed(s) for s in range(9001, 9010)}) >= 3)

    # B0-v1 untouched
    import hashlib
    b1 = hashlib.sha256(open(os.path.join(ROOT, "opponent_profiles.py"), "rb").read()).hexdigest()
    from strategy_library.policy_repository import get_policy_repository
    rep = get_policy_repository()
    check("B0-v1 artifact hash unchanged",
          rep.get_artifact("black-b0-v1")["opponent_module_hash"] == b1)

    print(f"\nRESULT {len(PASS)}/{len(PASS) + len(FAIL)} passed")
    sys.exit(0 if not FAIL else 1)


if __name__ == "__main__":
    main()
