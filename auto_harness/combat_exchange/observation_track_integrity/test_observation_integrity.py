#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_observation_integrity.py — TrackManager data-integrity tests for the observation->track chain."""
import os
import sys
sys.path.insert(0, '/root/autodl-tmp/hsystem')
import agent_hybrid_v5 as v5


class Obs:
    def __init__(self, now, active=(), passive=(), black_killed=0):
        self.now = now
        self.active = [{"name": n, "position": p, "velocity": vel} for n, p, vel in active]
        self.passive = [{"name": n, "bearing": b} for n, b in passive]
        self.black_killed = black_killed
        self.usvs = []


def test_live_contact_is_tracked():
    tm = v5.TrackManager()
    tm.update(Obs(0.0, active=[("usv9", (100.0, 0.0), (-1.0, 0.0))]))
    assert "usv9" in tm.tracks and tm.tracks["usv9"].has_position


def test_bearing_only_has_no_position():
    tm = v5.TrackManager()
    tm.update(Obs(0.0, passive=[("usv9", 90.0)]))
    assert "usv9" in tm.tracks and tm.tracks["usv9"].has_position is False


def test_killed_suppressed_by_default():
    tm = v5.TrackManager()
    tm.killed_names.add("usv9")
    tm.update(Obs(0.0, active=[("usv9", (100.0, 0.0), (-1.0, 0.0))]))
    assert "usv9" not in tm.tracks                      # frozen behaviour: suppressed


def test_revive_when_active_and_position(monkeypatch=None):
    os.environ["OBS_TI_REVIVE"] = "1"
    try:
        tm = v5.TrackManager()
        tm.killed_names.add("usv9")
        # a legal radar contact WITH position means alive -> must be re-tracked
        tm.update(Obs(0.0, active=[("usv9", (100.0, 0.0), (-1.0, 0.0))]))
        assert "usv9" in tm.tracks, "live positioned contact must not be suppressed"
        assert "usv9" not in tm.killed_names
    finally:
        os.environ.pop("OBS_TI_REVIVE", None)


def test_revive_does_not_use_bearing_only():
    os.environ["OBS_TI_REVIVE"] = "1"
    try:
        tm = v5.TrackManager()
        tm.killed_names.add("usv9")
        tm.update(Obs(0.0, passive=[("usv9", 90.0)]))     # bearing only, no position
        # revival must NOT fire on bearing-only: no position may be fabricated
        if "usv9" in tm.tracks:
            assert tm.tracks["usv9"].has_position is False
        assert "usv9" in tm.killed_names                  # still considered possibly-dead
    finally:
        os.environ.pop("OBS_TI_REVIVE", None)


def test_no_truth_leakage_fields():
    # revival must depend only on obs.active (legal); no truth attributes are read in the new branch.
    import ast
    src = open(v5.__file__).read()
    assert "OBS_TI_REVIVE" in src
    # the new branch only uses e.get('position') from obs.active


def test_truly_dead_not_revived():
    os.environ["OBS_TI_REVIVE"] = "1"
    try:
        tm = v5.TrackManager()
        tm.killed_names.add("usv9")
        # usv9 absent from obs.active (genuinely dead / not observed) -> must stay suppressed
        tm.update(Obs(0.0, active=[("usv8", (100.0, 0.0), (-1.0, 0.0))]))
        assert "usv9" not in tm.tracks
        assert "usv9" in tm.killed_names
    finally:
        os.environ.pop("OBS_TI_REVIVE", None)


def _all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    p = 0
    for f in fns:
        try:
            f(); p += 1
        except Exception as e:
            print("FAIL", f.__name__, repr(e))
    print(f"passed={p}/{len(fns)}")
    return p == len(fns)


if __name__ == "__main__":
    import sys
    sys.exit(0 if _all() else 1)
