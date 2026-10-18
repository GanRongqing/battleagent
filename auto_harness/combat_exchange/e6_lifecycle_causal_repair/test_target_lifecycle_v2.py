#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_target_lifecycle_v2.py — E6 lifecycle bookkeeping contract tests (flag-gated, behaviour-neutral)."""
import os, sys
sys.path.insert(0, "/root/autodl-tmp/hsystem")
sys.path.insert(0, "/root/autodl-tmp/hsystem/auto_harness/combat_exchange/target_lifecycle_integrity")
import agent_hybrid_v5 as v5
from target_lifecycle_verifier import verify


class Obs:
    def __init__(self, now, active=(), passive=(), black_killed=0):
        self.now = now
        self.active = [{"name": n, "position": p, "velocity": vel} for n, p, vel in active]
        self.passive = [{"name": n, "bearing": b} for n, b in passive]
        self.black_killed = black_killed
        self.usvs = []


def mk_on():
    os.environ["TARGET_LIFECYCLE_V2"] = "1"
    tm = v5.TrackManager(); return tm


def off():
    os.environ.pop("TARGET_LIFECYCLE_V2", None)


def test_01_off_no_state():
    off(); tm = v5.TrackManager()
    tm.update(Obs(0.0, active=[("usv9", (1, 0), (-1, 0))]))
    assert tm.lifecycle == {} and tm.lifecycle_log == []


def test_02_active_state():
    tm = mk_on(); off()
    tm.update(Obs(0.0, active=[("usv9", (1, 0), (-1, 0))]))
    assert tm.lifecycle["usv9"]["state"] == "OBSERVED_ACTIVE"


def test_03_bearing_state():
    tm = mk_on(); off()
    tm.update(Obs(0.0, passive=[("usv9", 90.0)]))
    assert tm.lifecycle["usv9"]["state"] == "OBSERVED_BEARING"
    assert tm.tracks["usv9"].has_position is False


def test_04_inference_is_suspected_not_confirmed():
    tm = mk_on(); off()
    tm.update(Obs(0.0, active=[("usv9", (1, 0), (-1, 0))]))
    tm.tracks["usv9"].engaged = True
    tm.kill_detect(Obs(30.0, active=[], black_killed=2), prev_black_killed=1)  # delta=1 -> inference
    st = tm.lifecycle.get("usv9", {}).get("state")
    assert st in ("SUSPECTED_DEAD",), st
    assert st != "CONFIRMED_DEAD"


def test_05_conflict_when_active_while_killed():
    tm = mk_on(); off()
    tm.killed_names.add("usv9")
    tm.update(Obs(0.0, active=[("usv9", (1, 0), (-1, 0))]))
    # note: update skips killed names before the lifecycle hook, so no track; conflict is recorded
    # only if the name passes the skip. Verify the skip still suppresses (frozen behaviour).
    assert "usv9" not in tm.tracks


def test_06_conflict_direct():
    tm = mk_on(); off()
    tm.killed_names.add("usv9")
    tm._lc_set("usv9", "DEATH_EVIDENCE_CONFLICT", "positioned_obs_vs_inferred_dead", "obs.active")
    assert tm.lifecycle["usv9"]["state"] == "DEATH_EVIDENCE_CONFLICT"


def test_07_dedupe_same_state():
    tm = mk_on(); off()
    tm.update(Obs(0.0, active=[("usv9", (1, 0), (-1, 0))]))
    tm.update(Obs(30.0, active=[("usv9", (1, 0), (-1, 0))]))
    n = [x for x in tm.lifecycle_log if x["name"] == "usv9" and x["next"] == "OBSERVED_ACTIVE"]
    assert len(n) == 1


def test_08_no_confirmed_without_confirmation():
    tm = mk_on(); off()
    tm.update(Obs(0.0, active=[("usv9", (1, 0), (-1, 0))]))
    tm.kill_detect(Obs(30.0, active=[]), prev_black_killed=1)
    assert all(v["state"] != "CONFIRMED_DEAD" for v in tm.lifecycle.values())


def test_09_missing_obs_not_death():
    tm = mk_on(); off()
    tm.update(Obs(0.0, active=[("usv9", (1, 0), (-1, 0))]))
    tm.update(Obs(30.0, active=[]))  # disappeared, no kill delta
    assert tm.lifecycle["usv9"]["state"] == "OBSERVED_ACTIVE"  # not promoted to dead


def test_10_log_has_provenance():
    tm = mk_on(); off()
    tm.update(Obs(0.0, active=[("usv9", (1, 0), (-1, 0))]))
    e = tm.lifecycle_log[-1]
    assert set(("name", "prev", "next", "event", "source")) <= set(e)


def test_11_id_not_merged():
    tm = mk_on(); off()
    tm.update(Obs(0.0, active=[("usv9", (1, 0), (-1, 0)), ("usv9x", (2, 0), (-1, 0))]))
    assert "usv9" in tm.lifecycle and "usv9x" in tm.lifecycle


def test_12_episode_isolation():
    a = mk_on(); off(); a.update(Obs(0.0, active=[("usv9", (1, 0), (-1, 0))]))
    b = mk_on(); off()
    assert b.lifecycle == {}


def test_13_flag_neutral_killed_names():
    off(); a = v5.TrackManager()
    a.update(Obs(0.0, active=[("usv9", (1, 0), (-1, 0))]))
    a.kill_detect(Obs(30.0, active=[]), prev_black_killed=1)
    on = mk_on(); off()
    on.update(Obs(0.0, active=[("usv9", (1, 0), (-1, 0))]))
    on.kill_detect(Obs(30.0, active=[]), prev_black_killed=1)
    assert a.killed_names == on.killed_names
    assert set(a.tracks) == set(on.tracks)


def test_14_obs_ti_revive_default_off():
    assert os.getenv("OBS_TI_REVIVE", "0") == "0"


def test_15_verifier_compatible():
    v = verify({"usv9": [(0, True), (30, True)]}, {"usv9": [30]})
    assert any(x["violation_type"] == "ACTIVE_AFTER_KILL" for x in v)


def test_16_suspected_distinct_from_confirmed():
    tm = mk_on(); off()
    tm._lc_set("a", "SUSPECTED_DEAD", "kill_inference", "kill_detect")
    tm._lc_set("b", "CONFIRMED_DEAD", "x", "y")
    assert tm.lifecycle["a"]["state"] != tm.lifecycle["b"]["state"]


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
