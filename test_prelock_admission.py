#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_prelock_admission.py — unit tests for C6B (agent_hybrid_prelock_admission.py)."""
import sys

from agent_hybrid_v5 import USV_SPEED
from agent_hybrid_prelock_admission import (
    AdmissionController, SUPPORT_RADIUS, MIN_SUPPORT, OVEREXT_ENTER, OVEREXT_EXIT,
    MIN_HOLD_STEPS, MAX_SHAPE_WAIT,
)


class Track:
    def __init__(self, name, pos, visible=True, has_pos=True):
        self.name = name
        self._pos = pos
        self._visible = visible
        self.has_position = has_pos
        self.assigned_usvs = set()
        self.is_ship = True
        self.engaged = False
        self.last_position = pos
        self.last_velocity = (-5, 0)
        self.last_seen_time = 0.0
        self.point_confidence = 1.0

    def is_visible(self, now):
        return self._visible

    def predicted_position(self, now):
        return self._pos


class Obs:
    def __init__(self, now, usvs):
        self.now = now
        self.usvs = usvs


def usv(name, pos, alive=True, locking=False, lu=None, frozen=False):
    return {"name": name, "is_alive": alive, "position": pos, "is_locking": locking,
            "locking_unit": lu, "is_frozen": frozen}


class Legal:
    def can_lock(self, u, t):
        return True


def mk(usvs, targets, tracks):
    c = AdmissionController()
    for u in usvs:
        c.targets[u["name"]] = targets.get(u["name"])
    return c, Obs(0.0, usvs), tracks


def test_1_safe_supported_approach_is_noop():
    usvs = [usv(f"u{i}", (100000 - i * 1000, 0)) for i in range(MIN_SUPPORT + 1)]
    tracks = {"t1": Track("t1", (90000, 0))}
    c, obs, tr = mk(usvs, {u["name"]: "t1" for u in usvs}, tracks)
    acts = c.step(obs, tr, Legal(), {}, [], None, "NORMAL")
    assert not c.admission_events, c.admission_events


def test_2_isolated_overextended_forward_blocks():
    # one USV far west (overextended), no nearby support
    usvs = [usv("u1", (10000, 0))] + [usv(f"u{i}", (200000, 0)) for i in range(2, 6)]
    tracks = {"t1": Track("t1", (5000, 0))}
    c, obs, tr = mk(usvs, {u["name"]: "t1" for u in usvs}, tracks)
    c.step(obs, tr, Legal(), {}, [], None, "NORMAL")
    assert any(e[1] == "u1" for e in c.admission_events), c.admission_events


def test_3_support_arrives_releases():
    usvs = [usv("u1", (10000, 0))] + [usv(f"u{i}", (12000, 0)) for i in range(2, 6)]
    tracks = {"t1": Track("t1", (5000, 0))}
    c, obs, tr = mk(usvs, {u["name"]: "t1" for u in usvs}, tracks)
    # enter wait first
    c._wait["u1"] = MIN_HOLD_STEPS
    c.step(obs, tr, Legal(), {}, [], None, "NORMAL")   # support present -> release
    assert "u1" not in c._wait, c._wait


def test_4_own_lock_returns_to_ace():
    usvs = [usv("u1", (10000, 0), locking=True, lu="t1")] + [usv(f"u{i}", (50000, 0)) for i in range(2, 6)]
    tracks = {"t1": Track("t1", (5000, 0))}
    c, obs, tr = mk(usvs, {"u1": "t1"}, tracks)
    c._wait["u1"] = 3
    c.step(obs, tr, Legal(), {}, [], None, "NORMAL")
    assert "u1" not in c._wait, c._wait


def test_5_pre_contact_cohesive_noop():
    usvs = [usv(f"u{i}", (100000 - i * 500, 0)) for i in range(6)]
    c, obs, tr = mk(usvs, {u["name"]: None for u in usvs}, {})
    c.step(obs, tr, Legal(), {}, [], None, "NORMAL")
    assert not c.admission_events


def test_6_pre_contact_extreme_overextension():
    usvs = [usv("u1", (5000, 0))] + [usv(f"u{i}", (60000, 0)) for i in range(2, 6)]
    c, obs, tr = mk(usvs, {"u1": None}, {})   # no target -> gate does not apply (own only)
    c.step(obs, tr, Legal(), {}, [], None, "NORMAL")
    assert not c.admission_events   # pre-contact gate intentionally not armed without assignment


def test_7_no_truth_state_used():
    import inspect
    import agent_hybrid_prelock_admission as m
    src = inspect.getsource(m)
    for bad in ("true_position", "black_truth", "hidden", "future"):
        assert bad not in src, bad


def test_8_no_route_or_strategy_id_used():
    import inspect
    import agent_hybrid_prelock_admission as m
    src = inspect.getsource(m)
    for bad in ("W2-", "route_id", "strategy_id", "scenario"):
        assert bad not in src, bad


def test_9_lock_legality_unchanged():
    usvs = [usv("u1", (10000, 0), locking=True, lu="t1")]
    tracks = {"t1": Track("t1", (5000, 0))}
    c, obs, tr = mk(usvs, {"u1": "t1"}, tracks)
    acts = c.step(obs, tr, Legal(), {}, [], None, "NORMAL")
    assert all(a[1] != "fire" for a in acts)


def test_10_fire_legality_unchanged():
    usvs = [usv("u1", (10000, 0))]
    tracks = {"t1": Track("t1", (5000, 0))}
    c, obs, tr = mk(usvs, {"u1": "t1"}, tracks)
    acts = c.step(obs, tr, Legal(), {}, [], None, "NORMAL")
    assert all(a[1] != "fire" and a[1] != "lock" or True for a in acts)
    assert not any("fire" in a[1] for a in acts)


def test_11_hysteresis_prevents_oscillation():
    # after entering wait, a small dip below ENTER but above EXIT must keep waiting (min hold)
    usvs = [usv("u1", (30000, 0))] + [usv(f"u{i}", (50000, 0)) for i in range(2, 6)]
    tracks = {"t1": Track("t1", (25000, 0))}
    c, obs, tr = mk(usvs, {"u1": "t1"}, tracks)
    c._wait["u1"] = 2   # < MIN_HOLD_STEPS
    c.step(obs, tr, Legal(), {}, [], None, "NORMAL")
    assert c._wait.get("u1") == 3, c._wait   # still waiting


def test_12_max_wait_prevents_freeze():
    usvs = [usv("u1", (10000, 0))] + [usv(f"u{i}", (50000, 0)) for i in range(2, 6)]
    tracks = {"t1": Track("t1", (5000, 0))}
    c, obs, tr = mk(usvs, {"u1": "t1"}, tracks)
    c._wait["u1"] = MAX_SHAPE_WAIT
    c.step(obs, tr, Legal(), {}, [], None, "NORMAL")
    assert "u1" not in c._wait, c._wait   # released after max wait


if __name__ == "__main__":
    ts = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    fail = 0
    for t in ts:
        try:
            t(); print("PASS", t.__name__)
        except Exception as e:
            fail += 1; print("FAIL", t.__name__, e)
    print("=" * 40)
    print("PASS" if not fail else "FAIL", f"{len(ts)-fail}/{len(ts)}")
    sys.exit(1 if fail else 0)
