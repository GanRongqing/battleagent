#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_w6_dev4_units.py — W6-dev4 commitment / reallocation invariants (T27-T36)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from anti_evasion.commitment import classify_platform, classify_all, FREE, SOFT, HARD, RESERVE  # noqa: E402
from anti_evasion.elastic_reserve import ElasticReserveManager, desired_reserve_capacity  # noqa: E402
from anti_evasion.releasable_pool import build_releasable_pool  # noqa: E402
from anti_evasion import config as cfg  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    if cond:
        PASS.append(name); print(f"  [PASS] {name}")
    else:
        FAIL.append(name); print(f"  [FAIL] {name} {detail}")


def usv(name, alive=True, locking=False, lockunit=None, frozen=False):
    return {"name": name, "is_alive": alive, "is_locking": locking,
            "locking_unit": lockunit if locking else None, "is_frozen": frozen}


# T27 FREE
def test_T27_free():
    print("== T27 unassigned alive USV -> FREE ==")
    c = classify_platform(usv("u1"), has_target=False)
    check("T27 FREE", c == FREE, c)
    c2 = classify_platform(usv("u1", alive=False), has_target=False)
    check("T27 dead not free (HARD)", c2 == HARD, c2)


# T28 SOFT
def test_T28_soft():
    print("== T28 has target, no lock/frozen -> SOFT ==")
    c = classify_platform(usv("u1"), has_target=True)
    check("T28 SOFT", c == SOFT, c)


# T29 HARD lock
def test_T29_hard_lock():
    print("== T29 active lock -> HARD ==")
    c = classify_platform(usv("u1", locking=True, lockunit="e1"), has_target=True)
    check("T29 HARD lock", c == HARD, c)


# T30 HARD frozen
def test_T30_hard_frozen():
    print("== T30 frozen -> HARD ==")
    c = classify_platform(usv("u1", frozen=True), has_target=True)
    check("T30 HARD frozen", c == HARD, c)


# T31 hard not releasable
def test_T31_hard_not_releasable():
    print("== T31 HARD never in candidate pool ==")
    obs = [usv("u1", locking=True, lockunit="e1"), usv("u2"), usv("u3")]
    tm = {"u1": "e1", "u2": None, "u3": None}
    cls = classify_all(obs, tm)
    pool, _ = build_releasable_pool(cls, tm, {"e1": ["u1"], "e2": ["u3"]}, {}, 0.0)
    check("T31 hard excluded from pool", "u1" not in pool, str(pool))
    check("T31 free included", "u2" in pool or "u3" in pool)


# T32 soft releasable
def test_T32_soft_releasable():
    print("== T32 SOFT with covered old target -> releasable ==")
    obs = [usv("u1"), usv("u2"), usv("u3")]
    tm = {"u1": "e1", "u2": None, "u3": None}
    cls = classify_all(obs, tm)
    pool, _ = build_releasable_pool(cls, tm, {"e1": ["u1", "u2"]}, {}, 0.0)
    check("T32 soft (covered target) enters pool", "u1" in pool, str(pool))


# T33 reserve release
def test_T33_reserve_release():
    print("== T33 risk resolved -> reserve released to FREE ==")
    rm = ElasticReserveManager()
    keep1, rel1, _ = rm.update(["u1", "u2", "u3", "u4"], 4, n_imminent=4, n_uncovered_feasible=1)
    keep2, rel2, _ = rm.update(["u1", "u2", "u3", "u4"], 4, n_imminent=0, n_uncovered_feasible=0)
    check("T33 reserve released when risk cleared", len(keep2) == 0 and rel2, str(keep2))
    check("T33 endgame capacity 0", desired_reserve_capacity(10, 1) == 0)


# T34 reserve create
def test_T34_reserve_create():
    print("== T34 uncovered critical -> reserve demand > 0 ==")
    check("T34 capacity>0 on critical", desired_reserve_capacity(10, 3, n_uncovered_feasible=1) > 0)
    check("T34 capacity 0 without risk", desired_reserve_capacity(10, 0) == 0)


# T35 endgame
def test_T35_endgame():
    print("== T35 single threat -> reserve 0 ==")
    check("T35 endgame reserve 0", desired_reserve_capacity(10, 1, 0) == 0)


# T36 no execution override under dev4
def test_T36_no_execution_override():
    print("== T36 dev4 leaves execution to legacy ==")
    check("T36 config dev4 => EXECUTION_OVERRIDE False",
          hasattr(cfg, "EXECUTION_OVERRIDE") and not (cfg.DEV4 and cfg.EXECUTION_OVERRIDE))
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "agent_hybrid_w6.py"), encoding="utf-8").read()
    check("T36 predictive-waypoint guarded (not in dev4)",
          "_w6_intercept = tuple(aim)" in src and "EXECUTION_OVERRIDE" in src)


def main():
    for t in (test_T27_free, test_T28_soft, test_T29_hard_lock, test_T30_hard_frozen,
              test_T31_hard_not_releasable, test_T32_soft_releasable,
              test_T33_reserve_release, test_T34_reserve_create,
              test_T35_endgame, test_T36_no_execution_override):
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
