#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_track_reacquire.py — unit tests for C5 (agent_hybrid_track_reacquire.py)."""
import sys

from agent_hybrid_track_reacquire import ReacquireController, MAX_REACQUIRE_TIME, U_MAX, _PredictorBank


class Track:
    def __init__(self, name, pos, vel, last_seen, visible, has_pos=True, unc=1000.0, man=0.0):
        self.name = name
        self.last_position = pos
        self.last_velocity = vel
        self.last_seen_time = last_seen
        self._visible = visible
        self.has_position = has_pos
        self._unc = unc
        self.maneuver_score = man
        self.assigned_usvs = set()
        self.is_ship = True
        self.engaged = False

    def is_visible(self, now):
        return self._visible

    def predicted_position(self, now):
        if self.last_position is None:
            return None
        dt = max(0.0, now - self.last_seen_time)
        return (self.last_position[0] + self.last_velocity[0] * dt,
                self.last_position[1] + self.last_velocity[1] * dt)

    def uncertainty(self, now):
        return self._unc


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


def _stale_ctrl(usv_target):
    c = ReacquireController()
    c.targets = dict(usv_target)
    return c


def test_1_fresh_identical_noop():
    # all targets fresh -> post-process must not alter actions vs parent result
    c = ReacquireController()
    c.targets = {"u1": "t1"}
    tr = {"t1": Track("t1", (100000, 0), (-10, 0), 0.0, visible=True)}
    obs = Obs(100.0, [usv("u1", (50000, 0))])
    acts = c.step(obs, tr, Legal(), {}, [], None, "NORMAL")
    assert all(a[1] in ("move", "lock") for a in acts)
    assert not c.reacq_events, c.reacq_events


def test_2_brief_stale_enters_reacquire():
    c = ReacquireController()
    c.targets = {"u1": "t1"}
    tr = {"t1": Track("t1", (100000, 0), (-10, 0), 50.0, visible=False, unc=2000.0)}
    obs = Obs(100.0, [usv("u1", (50000, 0))])   # stale 50s < 900 -> reacquire
    c.step(obs, tr, Legal(), {}, [], None, "NORMAL")
    assert len(c.reacq_events) == 1, c.reacq_events


def test_3_fresh_returns_exits_reacquire():
    c = ReacquireController()
    c.targets = {"u1": "t1"}
    stale = Track("t1", (100000, 0), (-10, 0), 50.0, visible=False, unc=2000.0)
    c.step(Obs(100.0, [usv("u1", (50000, 0))]), {"t1": stale}, Legal(), {}, [], None, "NORMAL")
    assert len(c.reacq_events) == 1
    fresh = Track("t1", (100000, 0), (-10, 0), 101.0, visible=True)
    c.step(Obs(101.0, [usv("u1", (50000, 0))]), {"t1": fresh}, Legal(), {}, [], None, "NORMAL")
    # no new reacquire event while fresh
    assert len(c.reacq_events) == 1


def test_4_timeout_expired():
    c = ReacquireController()
    c.targets = {"u1": "t1"}
    # stale_time will be 0 at first call; simulate expiry by pre-setting stale_since
    c._stale_since["u1"] = 0.0
    tr = {"t1": Track("t1", (100000, 0), (-10, 0), -800.0, visible=False, unc=2000.0)}
    obs = Obs(MAX_REACQUIRE_TIME + 10.0, [usv("u1", (50000, 0))])
    c.step(obs, tr, Legal(), {}, [], None, "NORMAL")
    assert not c.reacq_events, c.reacq_events   # EXPIRED -> parent semantics, no reacquire move


def test_5_uncertainty_expired():
    c = ReacquireController()
    c.targets = {"u1": "t1"}
    tr = {"t1": Track("t1", (100000, 0), (-10, 0), 50.0, visible=False, unc=U_MAX + 1.0)}
    c.step(Obs(100.0, [usv("u1", (50000, 0))]), tr, Legal(), {}, [], None, "NORMAL")
    assert not c.reacq_events, c.reacq_events


def test_6_predicted_cannot_create_lock():
    c = ReacquireController()
    c.targets = {"u1": "t1"}
    tr = {"t1": Track("t1", (100000, 0), (-10, 0), 50.0, visible=False, unc=2000.0)}
    acts = c.step(Obs(100.0, [usv("u1", (50000, 0))]), tr, Legal(), {}, [], None, "NORMAL")
    assert not any(a[1] == "lock" for a in acts), acts   # prediction drives MOVE only


def test_7_predicted_cannot_create_fire():
    c = ReacquireController()
    c.targets = {"u1": "t1"}
    tr = {"t1": Track("t1", (100000, 0), (-10, 0), 50.0, visible=False, unc=2000.0)}
    acts = c.step(Obs(100.0, [usv("u1", (50000, 0))]), tr, Legal(), {}, [], None, "NORMAL")
    assert not any(("fire" in a[1] or "hit" in a[1]) for a in acts), acts


def test_8_all_fresh_exact_noop():
    c = ReacquireController()
    c.targets = {"u1": "t1", "u2": "t2"}
    tr = {"t1": Track("t1", (100000, 0), (-10, 0), 99.0, visible=True),
          "t2": Track("t2", (100000, 50000), (-10, 0), 99.0, visible=True)}
    obs = Obs(100.0, [usv("u1", (50000, 0)), usv("u2", (50000, 50000))])
    c.step(obs, tr, Legal(), {}, [], None, "NORMAL")
    assert not c.reacq_events and not c._stale_since, (c.reacq_events, c._stale_since)


def test_9_non_assigned_stale_noop():
    c = ReacquireController()
    c.targets = {"u1": None}
    tr = {"t1": Track("t1", (100000, 0), (-10, 0), 50.0, visible=False, unc=2000.0)}
    c.step(Obs(100.0, [usv("u1", (50000, 0))]), tr, Legal(), {}, [], None, "NORMAL")
    assert not c.reacq_events, c.reacq_events


def test_10_allocator_ownership_restored_after_expired():
    c = ReacquireController()
    c.targets = {"u1": "t1"}
    tr = {"t1": Track("t1", (100000, 0), (-10, 0), -800.0, visible=False, unc=2000.0)}
    c._stale_since["u1"] = 0.0
    c.step(Obs(MAX_REACQUIRE_TIME + 10.0, [usv("u1", (50000, 0))]), tr, Legal(), {}, [], None, "NORMAL")
    assert c.targets.get("u1") == "t1"   # ownership unchanged; no sticky reacquire


def test_11_predictor_fallback_and_scoring():
    b = _PredictorBank()
    t = Track("t1", (100000, 0), (-10, 0), 0.0, visible=False)
    # no history -> fallback P0
    x, y, pid = b.predict("t1", 10.0, t)
    assert pid == "P0" and abs(x - 99900) < 1, (x, y, pid)
    b.score("t1", "P0", (99900, 0), (99901, 0))   # small error
    assert b.err[("t1", "P0")] < 5


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
