#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_target_lifecycle_verifier.py — tests for the offline Target Lifecycle Verifier."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from target_lifecycle_verifier import verify, summarize


def V(active, kills, revives=None):
    return verify(active, kills, revives)


def test_1_false_death():
    v = V({"usv9": [(0, True), (30, True), (60, True)]}, {"usv9": [30]})
    assert any(x["violation_type"] == "ACTIVE_AFTER_KILL" for x in v)


def test_2_dead_with_cached_position():
    # a target observed once then never again; kill later -> unverified (cached coordinate must not
    # be treated as a new live observation)
    v = V({"usv9": [(0, True)]}, {"usv9": [300]})
    types = {x["violation_type"] for x in v}
    assert "ACTIVE_AFTER_KILL" not in types
    assert "KILL_NO_REOBSERVATION" in types


def test_3_dead_still_in_current_observation():
    v = V({"usv9": [(0, True), (30, True)]}, {"usv9": [30]})
    assert any(x["violation_type"] == "ACTIVE_AFTER_KILL" for x in v)


def test_4_observed_to_stale():
    # no observation after t=0; verify does not invent a state -> no ACTIVE_AFTER_KILL
    v = V({"usv9": [(0, True)]}, {"usv9": [30]})
    assert not any(x["violation_type"] == "ACTIVE_AFTER_KILL" for x in v)


def test_5_timestamp_non_monotonic():
    v = V({"usv9": [(0, True), (60, True), (30, True)]}, {})
    assert any(x["violation_type"] == "TIMESTAMP_NON_MONOTONIC" for x in v)


def test_6_id_reuse_ambiguous():
    # two names tracked independently must not merge
    v = V({"usv9": [(0, True)], "usv9x": [(0, True)]}, {"usv9": [30]})
    assert all(x["target"] == "usv9" for x in v)


def test_7_conflicting_evidence_active_after_kill():
    v = V({"usv9": [(0, True), (30, True)]}, {"usv9": [10]})
    assert any(x["violation_type"] == "ACTIVE_AFTER_KILL" for x in v)


def test_8_duplicate_reports_deduped():
    v = V({"usv9": [(0, True), (30, True), (60, True)]}, {"usv9": [30, 30, 30]})
    cnt = [x for x in v if x["violation_type"] == "ACTIVE_AFTER_KILL"]
    assert len(cnt) == 1  # repeated reports are ONE event


def test_9_episode_isolation():
    a = V({"usv9": [(0, True)]}, {"usv9": [30]})
    b = V({"usv9": [(0, True)]}, {})
    assert b == []  # no cross-episode state


def test_10_no_truth_read():
    src = open(os.path.join(os.path.dirname(__file__), "target_lifecycle_verifier.py")).read().lower()
    for bad in ("engine_alive", "true_alive", "oracle", "black_usv_states", "ground_truth"):
        assert bad not in src
    # verifier only consumes active_series + kill/revive events (legal logs / agent bookkeeping)


def test_11_true_revival():
    v = V({"usv9": [(0, True), (30, True)]}, {"usv9": [30]}, {"usv9": [30]})
    assert any(x["violation_type"] == "INFO" and x["next_state"] == "TRUE_REVIVAL" for x in v)


def test_12_false_revival():
    v = V({"usv9": [(0, True)]}, {"usv9": [30]}, {"usv9": [90]})
    assert any(x["violation_type"] == "REVIVE_WITHOUT_ACTIVE" for x in v)


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
