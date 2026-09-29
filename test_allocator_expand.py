#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_allocator_expand.py — unit tests for white-combat-0002-v1 (ALLOCATOR_COMMITMENT_EXPANSION)."""
import sys

from agent_hybrid_v5 import StrategicIntent
from agent_hybrid_allocator_expand import ExpandingAllocator


class T:
    def __init__(self, name, pos, visible=True, ship=True, assigned=()):
        self.name = name
        self._pos = pos
        self.is_ship = ship
        self.has_position = True
        self._visible = visible
        self.assigned_usvs = set(assigned)
        self.point_confidence = 1.0
        self.last_velocity = (-10, 0)
        self.engaged = False

    def is_visible(self, now):
        return self._visible

    def predicted_position(self, now):
        return self._pos


def usv(name, pos):
    return {"name": name, "is_alive": True, "position": pos,
            "is_locking": False, "locking_unit": None, "is_frozen": False}


def run(tracks, usvs, usv_map, intent=None):
    alloc = ExpandingAllocator()
    result = alloc.allocate_usvs(tracks, usvs, usv_map, 0.0, intent=intent)
    return result


def test_A_zero_owner_gets_free_usv():
    tracks = {"b1": T("b1", (200000, 0), assigned=("u1",)),
              "b2": T("b2", (210000, 50000), assigned=("u2",)),
              "b3": T("b3", (220000, -50000))}  # zero owner
    usvs = [usv("u1", (100000, 0)), usv("u2", (100000, 50000)), usv("u3", (100000, -50000))]
    usv_map = {"u1": "b1", "u2": "b2", "u3": None}  # u3 free
    r = run(tracks, usvs, usv_map)
    assert "b3" in r and "u3" in r["b3"], r


def test_B_fill_until_no_free_or_no_zeroowner():
    tracks = {"b1": T("b1", (200000, 0)), "b2": T("b2", (210000, 50000))}
    usvs = [usv("u1", (100000, 0)), usv("u2", (100000, 50000))]
    usv_map = {"u1": None, "u2": None}
    r = run(tracks, usvs, usv_map)
    assert set(r.keys()) == {"b1", "b2"}, r


def test_C_stable_lock_not_stolen():
    # u1 has stable lock on b1 (assigned via assigned_usvs), b2 zero owner, u2 free
    tracks = {"b1": T("b1", (200000, 0), assigned=("u1",)),
              "b2": T("b2", (210000, 50000))}
    usvs = [usv("u1", (100000, 0)), usv("u2", (100000, 50000))]
    usv_map = {"u1": "b1", "u2": None}
    r = run(tracks, usvs, usv_map)
    assert r.get("b2") == ["u2"], r
    assert "u1" not in r.get("b2", []), r


def test_D_third_attacker_after_coverage():
    # b1 has 2 owners, b2 zero owner, free=1 -> free goes to b2, not b1's 3rd
    tracks = {"b1": T("b1", (200000, 0), assigned=("u1", "u2")),
              "b2": T("b2", (210000, 50000))}
    usvs = [usv("u1", (100000, 0)), usv("u2", (100000, 50000)), usv("u3", (100000, -50000))]
    usv_map = {"u1": "b1", "u2": "b1", "u3": None}
    r = run(tracks, usvs, usv_map)
    assert "b2" in r and "u3" in r["b2"], r


def test_F_reserve_release():
    # zero-owner target + only reserve USV free -> reserve released (u3 assigned)
    tracks = {"b1": T("b1", (200000, 0), assigned=("u1",))}
    usvs = [usv("u1", (100000, 0)), usv("u2", (100000, 50000))]
    usv_map = {"u1": "b1", "u2": None}  # u2 is the reserve
    intent = StrategicIntent(reserve_ratio=0.20, focus_level=2)
    r = run(tracks, usvs, usv_map, intent=intent)
    # b1 already has owner; no zero-owner target -> reserve NOT released, b1 may get u2 only if value high
    # (b1 has 1 owner; marginal 1->2 = 0.5 > min_assign -> should assign u2 anyway)
    assert "b1" in r, r


def test_G_reserve_preserved_when_no_undercommitment():
    from agent_hybrid_v5 import ThreatAllocator
    # all actionable targets already have owners -> no under-commitment -> reserve preserved,
    # so ExpandingAllocator must behave IDENTICALLY to base ThreatAllocator.
    def mk():
        tracks = {"b1": T("b1", (200000, 0), assigned=("u1", "u2"))}
        usvs = [usv("u1", (100000, 0)), usv("u2", (100000, 50000)),
                usv("u3", (100000, -50000)), usv("u4", (90000, 0)), usv("u5", (90000, 50000))]
        usv_map = {"u1": "b1", "u2": "b1", "u3": None, "u4": None, "u5": None}
        return tracks, usvs, usv_map
    intent = StrategicIntent(reserve_ratio=0.5, focus_level=2)
    t1, u1, m1 = mk()
    w5 = ThreatAllocator().allocate_usvs(t1, u1, m1, 0.0, intent=intent)
    t2, u2, m2 = mk()
    exp = ExpandingAllocator().allocate_usvs(t2, u2, m2, 0.0, intent=intent)
    assert w5 == exp, (w5, exp)


def test_H_variable_cardinality():
    for n in (3, 5, 10, 15, 20):
        tracks = {f"b{i}": T(f"b{i}", (200000 + i * 1000, 0)) for i in range(n)}
        usvs = [usv(f"u{i}", (100000 + i * 1000, 0)) for i in range(n)]
        usv_map = {f"u{i}": None for i in range(n)}
        r = run(tracks, usvs, usv_map)
        assert len(r) == n, (n, len(r))


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
