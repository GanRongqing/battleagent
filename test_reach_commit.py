#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_reach_commit.py — unit tests for white-combat-0005-v1 (REACHABILITY_WEIGHTED_COMMITMENT)."""
import sys

from agent_hybrid_v5 import StrategicIntent, ThreatAllocator, EMERGENCY_3V1_X
from agent_hybrid_allocator_expand import ExpandingAllocator
from agent_hybrid_reach_commit import ReachabilityAllocator


class T:
    def __init__(self, name, pos, visible=True, ship=True, assigned=(), conf=1.0, vel=(-10, 0)):
        self.name = name
        self._pos = pos
        self.is_ship = ship
        self.has_position = True
        self._visible = visible
        self.assigned_usvs = set(assigned)
        self.point_confidence = conf
        self.last_velocity = vel
        self.engaged = False

    def is_visible(self, now):
        return self._visible

    def predicted_position(self, now):
        return self._pos


def usv(name, pos):
    return {"name": name, "is_alive": True, "position": pos,
            "is_locking": False, "locking_unit": None, "is_frozen": False}


def reach_run(tracks, usvs, usv_map, intent=None):
    return ReachabilityAllocator().allocate_usvs(tracks, usvs, usv_map, 0.0, intent=intent)


def ace_run(tracks, usvs, usv_map, intent=None):
    return ExpandingAllocator().allocate_usvs(tracks, usvs, usv_map, 0.0, intent=intent)


def test_A_coverage_floor_unchanged():
    # two actionable targets (one near, one far) + 2 free => each must get >=1 attacker
    tracks = {"b1": T("b1", (200000, 0)), "b2": T("b2", (200000, 300000))}
    usvs = [usv("u1", (100000, 0)), usv("u2", (100000, 10000))]
    usv_map = {"u1": None, "u2": None}
    r = reach_run(tracks, usvs, usv_map)
    assert "b1" in r and "b2" in r, r


def test_B_reach_decay_prefers_near_target():
    # same breakthrough-proximity (same x) but very different travel distance
    tracks = {"b1": T("b1", (200000, 0)), "b2": T("b2", (200000, 300000))}
    usvs = [usv("u1", (100000, 0)), usv("u2", (100000, 10000)), usv("u3", (100000, 20000))]
    usv_map = {"u1": None, "u2": None, "u3": None}
    r = reach_run(tracks, usvs, usv_map)
    assert len(r.get("b2", [])) == 1, r   # far target gets only coverage, no 2nd attacker
    assert len(r.get("b1", [])) == 2, r   # near target receives the concentration


def test_C_urgent_target_exempt_from_decay():
    # target inside the urgent breakthrough line (x < URGENT_X) must still concentrate even if far
    tracks = {"b1": T("b1", (40000, 0))}
    usvs = [usv("u1", (200000, 0)), usv("u2", (200000, 10000))]
    usv_map = {"u1": None, "u2": None}
    r = reach_run(tracks, usvs, usv_map)
    assert len(r.get("b1", [])) == 2, r


def test_D_matches_ace_when_all_near():
    # when every target is reachable, C4 must equal ACE (mechanism is a no-op)
    def mk():
        tracks = {"b1": T("b1", (150000, 0)), "b2": T("b2", (150000, 20000))}
        usvs = [usv("u1", (140000, 0)), usv("u2", (140000, 10000)), usv("u3", (140000, 20000))]
        usv_map = {"u1": None, "u2": None, "u3": None}
        return tracks, usvs, usv_map
    t1, u1, m1 = mk(); a = ace_run(t1, u1, m1)
    t2, u2, m2 = mk(); c = reach_run(t2, u2, m2)
    assert a == c, (a, c)


def test_E_reach_factor_bounds():
    a = ReachabilityAllocator()
    # nearest free ~0 -> reach ~1 ; nearest far -> reach floor
    t = T("b", (200000, 0))
    near = [usv("u1", (200000, 0))]
    far = [usv("u1", (0, 0))]
    assert abs(a._reach_factor(t, 0.0, near, {"u1": None}) - 1.0) < 1e-6
    assert abs(a._reach_factor(t, 0.0, far, {"u1": None}) - a.REACH_FLOOR) < 1e-6


def test_F_no_free_usv_noop():
    tracks = {"b1": T("b1", (200000, 0), assigned=("u1",))}
    usvs = [usv("u1", (100000, 0))]
    usv_map = {"u1": "b1"}
    r = reach_run(tracks, usvs, usv_map)
    assert r == {}, r


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print("PASS %s" % t.__name__)
        except Exception as e:
            failed += 1
            print("FAIL %s: %s" % (t.__name__, e))
    print("=" * 40)
    print("PASS" if failed == 0 else "FAIL", "%d/%d" % (len(tests) - failed, len(tests)))
    sys.exit(1 if failed else 0)
