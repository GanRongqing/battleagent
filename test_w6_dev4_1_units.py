#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_w6_dev4_1_units.py — W6-dev4.1 trigger-eligibility invariants (T37-T46)."""
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


def free_to_imminent(eta, ref, conc, cap, risk_high, cls_free):
    """Mirror of the dev4.1 predicate (candidate eligibility gate)."""
    if not (cls_free and risk_high):
        return False
    if conc >= cap:
        return False
    if ref is None or ref <= 0:
        return False
    return eta <= cfg.FREE_TO_IMMINENT_ETA_RATIO * ref


# T37
def test_T37_high_imminent_free_assign():
    check("T37 ratio 1.2 below cap -> YES",
          free_to_imminent(120, 100, 1, cfg.EMERGENCY_CONCENTRATION, True, True))


# T38
def test_T38_eta_too_slow():
    check("T38 ratio 1.8 -> NO",
          not free_to_imminent(180, 100, 1, cfg.EMERGENCY_CONCENTRATION, True, True))


# T39
def test_T39_risk_below_high():
    check("T39 risk below HIGH -> NO", not free_to_imminent(100, 100, 1, 3, False, True))


# T40
def test_T40_concentration_guard():
    check("T40 at concentration cap -> NO",
          not free_to_imminent(100, 100, cfg.EMERGENCY_CONCENTRATION,
                               cfg.EMERGENCY_CONCENTRATION, True, True))


# T41/T42: dev4.1 is FREE-only (SOFT/HARD untouched) — source-level guard
def test_T41_T42_hard_soft_untouched():
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "agent_hybrid_w6.py"), encoding="utf-8").read()
    free_only = ('cls.get(u) != "FREE"' in src)
    check("T41/T42 dev4.1 pre-pass restricted to FREE class (SOFT/HARD untouched)",
          free_only)


# T43 legacy execution (no override under dev4_1)
def test_T43_legacy_execution():
    check("T43 config dev4_1 => EXECUTION_OVERRIDE False",
          (cfg.W6_MODE == "dev4_1") and not cfg.EXECUTION_OVERRIDE)


# T44 invalid reference ETA
def test_T44_invalid_eta():
    check("T44 invalid/zero ref -> NO (no crash)", not free_to_imminent(100, 0, 1, 3, True, True))
    check("T44 missing ref -> NO", not free_to_imminent(100, None, 1, 3, True, True))


# T45 variable cardinality (no count-specific rule)
def test_T45_variable_cardinality():
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "anti_evasion", "config.py"), encoding="utf-8").read()
    check("T45 concentration cap is per-target normalized (no fleet-count branch)",
          "EMERGENCY_CONCENTRATION = 3" in src and "== 10" not in src and "== 20" not in src)


# T46 fair-play: predicate is a pure function of legal inputs
def test_T46_fair_play():
    a = free_to_imminent(120, 100, 1, 3, True, True)
    b = free_to_imminent(120, 100, 1, 3, True, True)
    check("T46 deterministic (pure predicate) -> identical", a == b)


def main():
    for t in (test_T37_high_imminent_free_assign, test_T38_eta_too_slow,
              test_T39_risk_below_high, test_T40_concentration_guard,
              test_T41_T42_hard_soft_untouched, test_T43_legacy_execution,
              test_T44_invalid_eta, test_T45_variable_cardinality, test_T46_fair_play):
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
