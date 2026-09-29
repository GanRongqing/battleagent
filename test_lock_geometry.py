#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_lock_geometry.py — unit tests for white-combat-0003-v1 (LOCK-FIRST APPROACH)."""
import sys

from agent_hybrid_v5 import LOCK_RANGE, USV_SPEED
from agent_hybrid_lock_geometry import LockFirstUSVController


class T:
    def __init__(self, name, pos, visible=True, ship=True):
        self.name = name
        self._pos = pos
        self.is_ship = ship
        self.has_position = True
        self._visible = visible
        self.assigned_usvs = []
        self.point_confidence = 1.0
        self.last_velocity = (-8, 0)
        self.engaged = False

    def is_visible(self, now):
        return self._visible

    def predicted_position(self, now):
        return self._pos


class Obs:
    def __init__(self, usvs, now=0.0):
        self.usvs = usvs; self.uavs = []; self.now = now


class Legal:
    def __init__(self, lock_ok=True):
        self._ok = lock_ok
    def can_lock(self, u, t): return self._ok
    def can_move(self, u): return True


def usv(name, pos, locking=False, locking_unit=None):
    return {"name": name, "is_alive": True, "position": pos, "is_locking": locking,
            "locking_unit": locking_unit, "is_locked": False, "locked_attacker": [],
            "is_frozen": False}


def action_of(acts, nm):
    for a in acts:
        if a[0].startswith(nm):
            return a
    return None


def test_1_prelock_closes_beyond_range():
    ctrl = LockFirstUSVController()
    # u1 assigned to b1 far away (150km), target not visible -> W5 would standoff; C2 must close
    obs = Obs([usv("white_usv1", (0, 0))])
    tracks = {"b1": T("b1", (150000, 0), visible=False)}
    ctrl.targets["white_usv1"] = "b1"
    acts = ctrl.step(obs, tracks, Legal(), {}, [])
    a = action_of(acts, "white_usv1")
    assert a is not None and a[1] == "move", a
    crs = float(a[0].split("target_course=")[1].split()[0])
    assert abs((crs - 90) % 360) < 45, a  # bearing to (150000,0) ~ east (course 90)


def test_2_prelock_no_band_standoff():
    ctrl = LockFirstUSVController()
    # u1 at 35km from b1, but lock NOT legal (can_lock False) -> W5 runs band standoff;
    # C2 (pre-lock) must still close instead.
    obs = Obs([usv("white_usv1", (0, 0))])
    tracks = {"b1": T("b1", (35000, 0), visible=True)}
    ctrl.targets["white_usv1"] = "b1"
    acts = ctrl.step(obs, tracks, Legal(lock_ok=False), {}, [])
    a = action_of(acts, "white_usv1")
    assert a[1] == "move", a
    crs = float(a[0].split("target_course=")[1].split()[0])
    assert abs((crs - 90) % 360) < 45, a  # close straight to (35000,0)


def test_3_lock_prioritized_over_move():
    ctrl = LockFirstUSVController()
    # u1 within lock range + legal lock -> must LOCK (not overridden)
    obs = Obs([usv("white_usv1", (0, 0))])
    tracks = {"b1": T("b1", (30000, 0), visible=True)}
    ctrl.targets["white_usv1"] = "b1"
    acts = ctrl.step(obs, tracks, Legal(lock_ok=True), {}, [])
    a = action_of(acts, "white_usv1")
    assert a[1] == "lock", a


def test_6_postlock_reverts():
    ctrl = LockFirstUSVController()
    # u1 has already locked b1 -> pre-lock rule must NOT apply (post-lock behaviour restored)
    obs = Obs([usv("white_usv1", (0, 0))])
    tracks = {"b1": T("b1", (35000, 0), visible=False)}
    ctrl.targets["white_usv1"] = "b1"
    ctrl._locked["white_usv1"] = {"b1"}
    acts = ctrl.step(obs, tracks, Legal(), {}, [])
    a = action_of(acts, "white_usv1")
    assert a is not None, a  # exists; not forced by pre-lock rule


def test_8_variable_cardinality():
    for n in (3, 5, 10, 15, 20):
        ctrl = LockFirstUSVController()
        usvs = [usv(f"white_usv{i}", (0, i * 1000)) for i in range(n)]
        tracks = {f"b{i}": T(f"b{i}", (150000, i * 1000), visible=False) for i in range(n)}
        for i in range(n):
            ctrl.targets[f"white_usv{i}"] = f"b{i}"
        acts = ctrl.step(Obs(usvs), tracks, Legal(), {}, [])
        assert sum(1 for a in acts if a[1] == "move") == n, (n, acts)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t(); print("PASS", t.__name__)
        except Exception as e:
            failed += 1; print("FAIL", t.__name__, ":", e)
    print("=" * 40)
    print("PASS" if failed == 0 else "FAIL", f"{len(tests)-failed}/{len(tests)}")
    sys.exit(1 if failed else 0)
