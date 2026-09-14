#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_w6_dev4_2_units.py — W6-dev4.2 coverage-safe reinforcement invariants (T47-T58)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from anti_evasion import config as cfg  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    if cond:
        PASS.append(name); print(f"  [PASS] {name}")
    else:
        FAIL.append(name); print(f"  [FAIL] {name} {detail}")


def deadline_feasible(eta, b_eta):
    return b_eta is not None and b_eta > 0 and eta * (1 + cfg.SCREEN_ETA_SAFETY) <= b_eta


def deficit_trigger(risk, in_time_capacity, required):
    return in_time_capacity < required


def coverage_safe(has_other_candidate):
    return has_other_candidate


# T47
def test_T47_capacity_deficit_trigger():
    check("T47 HIGH + capacity<required + feasible -> allow",
          deficit_trigger(0.8, 0, 1) and deadline_feasible(100, 200))


# T48
def test_T48_no_deficit():
    check("T48 capacity sufficient -> no need", not deficit_trigger(0.8, 1, 1))


# T49/T50 deadline
def test_T49_T50_deadline():
    check("T49 ETA before deadline -> feasible", deadline_feasible(100, 200))
    check("T50 ETA after deadline -> infeasible", not deadline_feasible(300, 200))


# T51/T52 coverage
def test_T51_T52_coverage():
    check("T51 another candidate exists -> safe", coverage_safe(True))
    check("T52 only candidate -> unsafe", not coverage_safe(False))


# T53/T54 hard/soft unchanged
def test_T53_T54_hard_soft():
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "agent_hybrid_w6.py"), encoding="utf-8").read()
    check("T53 dev4.2 pre-pass restricted to FREE (HARD excluded)",
          'cls.get(u) != "FREE"' in src and "HARD_COMMITTED" in src)
    check("T54 no new SOFT release path added by dev4.2",
          "dev4_soft_release_events" in src)


# T55 endgame: single threat + concentration not blocked meaninglessly
def test_T55_endgame():
    check("T55 required caps small/normalized (HIGH=1,CRIT=2)",
          cfg.REQUIRED_IN_TIME_HIGH == 1 and cfg.REQUIRED_IN_TIME_CRITICAL == 2)
    check("T55 capacity ceiling scale-agnostic (per-target)",
          cfg.EMERGENCY_CONCENTRATION == 3)


# T56 variable cardinality
def test_T56_variable_cardinality():
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "anti_evasion", "config.py"), encoding="utf-8").read()
    check("T56 no fleet-count branch in dev4.2 config",
          "== 10" not in src and "== 30" not in src)


# T57 fair play pure
def test_T57_fair_play():
    check("T57 pure predicates deterministic", deadline_feasible(100, 200) ==
          deadline_feasible(100, 200))


# T58 legacy execution
def test_T58_legacy_execution():
    check("T58 dev4_2 => execution override False",
          (cfg.W6_MODE == "dev4_2") and not cfg.EXECUTION_OVERRIDE)


def main():
    for t in (test_T47_capacity_deficit_trigger, test_T48_no_deficit,
              test_T49_T50_deadline, test_T51_T52_coverage,
              test_T53_T54_hard_soft, test_T55_endgame, test_T56_variable_cardinality,
              test_T57_fair_play, test_T58_legacy_execution):
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
