#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_lifecycle_handoff_v1.py — E7 interface handoff tests (LIFECYCLE_HANDOFF_V1)."""
import os, sys
sys.path.insert(0, "/root/autodl-tmp/hsystem")
import agent_hybrid_v5 as v5


class Obs:
    def __init__(self, now, active=(), passive=(), black_killed=0):
        self.now = now
        self.active = [{"name": n, "position": p, "velocity": vel} for n, p, vel in active]
        self.passive = [{"name": n, "bearing": b} for n, b in passive]
        self.black_killed = black_killed
        self.usvs = []


def clear_flags():
    for k in ("LIFECYCLE_HANDOFF_V1", "OBS_TI_REVIVE", "TARGET_LIFECYCLE_V2"):
        os.environ.pop(k, None)


def fresh(killed=(), kill_global=()):
    tm = v5.TrackManager()
    tm.killed_names.update(killed)
    v5._KILLED.clear(); v5._KILLED.update(kill_global)
    return tm


def test_01_off_no_revive():
    tm = fresh(killed=["usv13"], kill_global=["usv13"])
    tm.update(Obs(0.0, active=[("usv13", (1, 0), (-1, 0))]))
    assert "usv13" not in tm.tracks and "usv13" in tm.killed_names


def test_02_on_revives_both_stores():
    clear_flags(); os.environ["LIFECYCLE_HANDOFF_V1"] = "1"
    tm = fresh(killed=["usv13"], kill_global=["usv13"])
    tm.update(Obs(0.0, active=[("usv13", (1, 0), (-1, 0))]))
    assert "usv13" in tm.tracks
    assert "usv13" not in tm.killed_names
    assert "usv13" not in v5._KILLED, "second store must be cleared too"
    clear_flags()


def test_03_legacy_revive_leaves_second_store_stale():
    clear_flags(); os.environ["OBS_TI_REVIVE"] = "1"
    tm = fresh(killed=["usv13"], kill_global=["usv13"])
    tm.update(Obs(0.0, active=[("usv13", (1, 0), (-1, 0))]))
    assert "usv13" not in tm.killed_names
    assert "usv13" in v5._KILLED, "documents the pre-E7 inconsistency"
    clear_flags()


def test_04_no_position_no_revive():
    clear_flags(); os.environ["LIFECYCLE_HANDOFF_V1"] = "1"
    tm = fresh(killed=["usv13"], kill_global=["usv13"])
    tm.update(Obs(0.0, passive=[("usv13", 90.0)]))
    if "usv13" in tm.tracks:
        assert tm.tracks["usv13"].has_position is False
    assert "usv13" in v5._KILLED
    clear_flags()


def test_05_no_confirmed_created():
    clear_flags(); os.environ["LIFECYCLE_HANDOFF_V1"] = "1"; os.environ["TARGET_LIFECYCLE_V2"] = "1"
    tm = fresh(killed=["usv13"], kill_global=["usv13"])
    tm.update(Obs(0.0, active=[("usv13", (1, 0), (-1, 0))]))
    assert all(v["state"] != "CONFIRMED_DEAD" for v in tm.lifecycle.values())
    clear_flags()


def test_06_episode_isolation():
    clear_flags(); os.environ["LIFECYCLE_HANDOFF_V1"] = "1"
    a = fresh(killed=["usv13"], kill_global=["usv13"]); a.update(Obs(0.0, active=[("usv13", (1, 0), (-1, 0))]))
    b = fresh()
    assert b.killed_names == set() and v5._KILLED == set() and b.lifecycle == {}
    clear_flags()


def test_07_idempotent():
    clear_flags(); os.environ["LIFECYCLE_HANDOFF_V1"] = "1"; os.environ["TARGET_LIFECYCLE_V2"] = "1"
    tm = fresh(killed=["usv13"], kill_global=["usv13"])
    tm.update(Obs(0.0, active=[("usv13", (1, 0), (-1, 0))]))
    n1 = len([x for x in tm.lifecycle_log if x["next"] == "OBSERVED_ACTIVE"])
    tm.update(Obs(30.0, active=[("usv13", (1, 0), (-1, 0))]))
    n2 = len([x for x in tm.lifecycle_log if x["next"] == "OBSERVED_ACTIVE"])
    assert n1 == n2
    clear_flags()


def test_08_no_truth_tokens():
    src = open(v5.__file__).read().lower()
    # the new branch only reads obs.active positions and the two stores
    assert "revive_via_legal_obs" in src
    for bad in ("engine_alive", "true_alive", "oracle"):
        assert bad not in src


def test_09_flag_off_equivalence():
    clear_flags()
    a = fresh(); a.update(Obs(0.0, active=[("usv9", (1, 0), (-1, 0))]))
    clear_flags()
    b = fresh(); b.update(Obs(0.0, active=[("usv9", (1, 0), (-1, 0))]))
    assert set(a.tracks) == set(b.tracks) and a.killed_names == b.killed_names == set()


def test_10_handoff_overrides_legacy():
    clear_flags(); os.environ["LIFECYCLE_HANDOFF_V1"] = "1"; os.environ["OBS_TI_REVIVE"] = "1"
    tm = fresh(killed=["usv13"], kill_global=["usv13"])
    tm.update(Obs(0.0, active=[("usv13", (1, 0), (-1, 0))]))
    assert "usv13" not in v5._KILLED
    clear_flags()


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
    sys.exit(0 if _all() else 1)
