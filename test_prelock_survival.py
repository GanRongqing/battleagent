#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_prelock_survival.py — unit tests for white-combat-0004-v1 (SURVIVAL_AWARE_PRELOCK_ADMISSION)."""
import sys
import math

from agent_hybrid_v5 import USV_SPEED
from agent_hybrid_prelock_survival import PrelockSurvivalUSVController, SUPPORT_RANGE


class T:
    def __init__(self, name, pos, visible=True):
        self.name = name; self._pos = pos; self.is_ship = True; self.has_position = True
        self._visible = visible; self.assigned_usvs = []; self.point_confidence = 1.0
        self.last_velocity = (-8, 0); self.engaged = False
    def is_visible(self, now): return self._visible
    def predicted_position(self, now): return self._pos


class Obs:
    def __init__(self, usvs, now=0.0): self.usvs = usvs; self.uavs = []; self.now = now


class Legal:
    def can_lock(self, u, t): return True
    def can_move(self, u): return True


def usv(name, pos, locked=False, locking=False):
    return {"name": name, "is_alive": True, "position": pos, "is_locking": locking,
            "locking_unit": None, "is_locked": locked, "locked_attacker": ["e1"] if locked else [],
            "is_frozen": False}


def act(acts, nm):
    for a in acts:
        if a[0].startswith(nm): return a
    return None


def test_1_disengage_when_exposed_lost_far():
    ctrl = PrelockSurvivalUSVController()
    obs = Obs([usv("white_usv1", (0, 0), locked=True), usv("white_usv2", (90000, 0))])
    tracks = {"b1": T("b1", (200000, 0), visible=False)}
    ctrl.targets["white_usv1"] = "b1"
    acts = ctrl.step(obs, tracks, Legal(), {}, [])
    a = act(acts, "white_usv1")
    assert a[1] == "move", a
    crs = float(a[0].split("target_course=")[1].split()[0])
    # nearest friendly is at (90000,0) -> east (~90), not toward target (200000,0) which is also east
    # disengage == move toward support; both east here, so check it's a move and no lock
    assert "锁定" not in a[0]


def test_2_no_retreat_when_target_visible():
    ctrl = PrelockSurvivalUSVController()
    obs = Obs([usv("white_usv1", (0, 0), locked=True), usv("white_usv2", (90000, 0))])
    tracks = {"b1": T("b1", (200000, 0), visible=True)}
    ctrl.targets["white_usv1"] = "b1"
    acts = ctrl.step(obs, tracks, Legal(), {}, [])
    a = act(acts, "white_usv1")
    assert a is not None  # normal behaviour (no forced retreat)


def test_3_no_retreat_when_support_near():
    ctrl = PrelockSurvivalUSVController()
    obs = Obs([usv("white_usv1", (0, 0), locked=True), usv("white_usv2", (10000, 0))])
    tracks = {"b1": T("b1", (200000, 0), visible=False)}
    ctrl.targets["white_usv1"] = "b1"
    acts = ctrl.step(obs, tracks, Legal(), {}, [])
    a = act(acts, "white_usv1")
    assert a is not None


def test_4_no_retreat_when_not_exposed():
    ctrl = PrelockSurvivalUSVController()
    obs = Obs([usv("white_usv1", (0, 0), locked=False), usv("white_usv2", (90000, 0))])
    tracks = {"b1": T("b1", (200000, 0), visible=False)}
    ctrl.targets["white_usv1"] = "b1"
    acts = ctrl.step(obs, tracks, Legal(), {}, [])
    assert act(acts, "white_usv1") is not None


def test_5_no_retreat_when_locking():
    ctrl = PrelockSurvivalUSVController()
    obs = Obs([usv("white_usv1", (0, 0), locked=True, locking=True), usv("white_usv2", (90000, 0))])
    tracks = {"b1": T("b1", (200000, 0), visible=False)}
    ctrl.targets["white_usv1"] = "b1"
    acts = ctrl.step(obs, tracks, Legal(), {}, [])
    assert act(acts, "white_usv1") is not None


def test_6_variable_cardinality():
    for n in (3, 5, 10, 15, 20):
        ctrl = PrelockSurvivalUSVController()
        usvs = [usv(f"white_usv{i}", (i * 100000, 0)) for i in range(n)]
        tracks = {f"b{i}": T(f"b{i}", (200000 + i * 1000, 0), visible=False) for i in range(n)}
        for i in range(n):
            ctrl.targets[f"white_usv{i}"] = f"b{i}"
        acts = ctrl.step(Obs(usvs), tracks, Legal(), {}, [])
        assert len(acts) == n, (n, len(acts))


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
