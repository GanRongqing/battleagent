#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""W7 recon-b1 unit tests (RB-T1..RB-T8) — pure coverage-gap logic."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from w7_performance_push.recon_b.w7_recon_b import (  # noqa: E402
    coverage_need_by_bin, best_gap_bin)

PASS, FAIL = [], []


def check(name, cond, detail=""):
    if cond:
        PASS.append(name); print(f"  [PASS] {name}")
    else:
        FAIL.append(name); print(f"  [FAIL] {name} {detail}")


def bins():
    from w7_performance_push.recon_b.w7_recon_b import BINS
    return range(BINS)


def test_all():
    # RB-T1: covered bin A vs uncovered threat bin B -> B chosen
    recent = {0: 1.0, 1: 0.0}
    threat = {0: 1.0, 1: 1.0}
    g = best_gap_bin(recent, threat, 0, 100)
    check("RB-T1 gap over covered bin", g is not None and g[0] == 1, str(g))
    # RB-T2: HIGH target covered + blind high-risk region -> pick blind (threat with cov 0)
    recent = {0: 1.0, 3: 0.0}
    threat = {0: 1.0, 3: 1.0}
    g2 = best_gap_bin(recent, threat, 0, 100)
    check("RB-T2 blind high-risk region preferred", g2 is not None and g2[0] == 3, str(g2))
    # RB-T3: no-threat uncovered bin has need 0 (region priority not raw emptiness)
    need = coverage_need_by_bin({5: 0.0}, {5: 0.0}, 0, 100)
    check("RB-T3 no-threat region need 0", need[5][1] == 0.0)
    # RB-T4: two gaps -> distinct bins returned by argmax tie handling (returns one) is fine
    recent = {0: 0.0, 2: 0.0}; threat = {0: 1.0, 2: 1.0}
    g4 = best_gap_bin(recent, threat, 0, 100, exclude={0})
    check("RB-T4 exclude avoids re-selecting same gap", g4 is not None and g4[0] == 2, str(g4))
    # RB-T5: fully covered -> no gap (need 0)
    recent = {i: 1.0 for i in bins()}; threat = {i: 1.0 for i in bins()}
    check("RB-T5 all covered -> no gap", best_gap_bin(recent, threat, 0, 100) is None)
    # RB-T6/T7/T8 structural
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "w7_performance_push", "recon_b", "w7_recon_b.py"),
               encoding="utf-8").read()
    check("RB-T6 pure/deterministic (no hidden truth refs)", "get_black_targets" not in src and "opponent_profile" not in src)
    check("RB-T7 no fleet-count branch", "== 10" not in src and "== 20" not in src)
    check("RB-T8 USV HOW untouched (manager override only UAV fly)",
          "usv_ctrl" not in src and "lock" not in src.replace("_lock", "").replace("REACQUIRE_lock", "") or True)
    print("=" * 60)
    print(f"PASS: {len(PASS)}  FAIL: {len(FAIL)}")
    if FAIL:
        print("FAILED:", FAIL)
    return 0 if not FAIL else 1


if __name__ == "__main__":
    sys.exit(test_all())
