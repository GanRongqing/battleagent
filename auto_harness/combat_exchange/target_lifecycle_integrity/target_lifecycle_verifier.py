#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""target_lifecycle_verifier.py — OFFLINE, READ-ONLY target-lifecycle integrity checker.

It never runs inside the agent. It reconciles, from existing logs, the Agent's death bookkeeping
(`killed_names` / [KILL] events) against the legal radar observation stream (`obs.active` /
game-log `active_enemies`).

Engine fact used (source-verified):
  - `entity.kill()` sets `isactive=False` (hsystem/simulation/core/entity.pyx:33-35)
  - radar only scans `engine.actives()` (isactive units) (radar.pyx:261/631)
  => a unit present in the radar observation with a position is ALIVE (modulo a <=1-tick in-tick
     ordering artifact). Therefore "KILL then still-observed" = FALSE_DEATH, not a ghost.

Usage:
  verify(active_series, kill_events) -> list of violation dicts
"""
from collections import defaultdict


def verify(active_series, kill_events, revive_events=None, tick_tol=1):
    """active_series: {target: [(sim_time, has_position), ...]} (sorted)
       kill_events:    {target: [sim_time, ...]}
       revive_events:  {target: [sim_time, ...]} or None
    Returns violations: [{target, sim_time, previous_state, input_event, evidence_source,
                          next_state, violation_type, reason}]
    """
    out = []
    active_times = {t: sorted(ts for ts, _ in v) for t, v in active_series.items()}
    # monotonicity over the RAW observation order (all targets)
    for tgt, v in active_series.items():
        at = [ts for ts, _ in v]
        for i in range(1, len(at)):
            if at[i] < at[i - 1]:
                out.append(dict(target=tgt, sim_time=at[i], previous_state="OBSERVED",
                                input_event="active_observation", evidence_source="game_log.active_enemies",
                                next_state="OBSERVED", violation_type="TIMESTAMP_NON_MONOTONIC",
                                reason=f"{at[i]} < {at[i-1]}"))
    for tgt, times in kill_events.items():
        at = active_times.get(tgt, [])
        for tk in times:
            later = [x for x in at if x >= tk]
            if later:
                out.append(dict(target=tgt, sim_time=tk, previous_state="ALIVE_OBSERVED",
                                input_event="agent_kill_flag", evidence_source="agent stdout [KILL]",
                                next_state="FALSE_DEATH", violation_type="ACTIVE_AFTER_KILL",
                                reason=f"still observed at t={later[0]} (active=>alive)"))
            else:
                out.append(dict(target=tgt, sim_time=tk, previous_state="OBSERVED",
                                input_event="agent_kill_flag", evidence_source="agent stdout [KILL]",
                                next_state="UNVERIFIED_DEATH", violation_type="KILL_NO_REOBSERVATION",
                                reason="no later active observation; engine truth not logged"))
    if revive_events:
        for tgt, times in revive_events.items():
            at = active_times.get(tgt, [])
            for tr in times:
                # A revive is only legitimate if the target is actually active (positioned) near tr.
                near = [x for x in at if abs(x - tr) <= _tol(at, tick_tol)]
                if not near:
                    out.append(dict(target=tgt, sim_time=tr, previous_state="KILLED",
                                    input_event="revive_flag", evidence_source="agent revive",
                                    next_state="FALSE_REVIVAL", violation_type="REVIVE_WITHOUT_ACTIVE",
                                    reason="revived without a current positioned observation"))
                else:
                    out.append(dict(target=tgt, sim_time=tr, previous_state="KILLED",
                                    input_event="revive_flag", evidence_source="agent revive",
                                    next_state="TRUE_REVIVAL", violation_type="INFO",
                                    reason=f"revived with live observation at {near[0]}"))
    # dedupe identical (target, violation_type, sim_time) — repeated per-step logs are ONE event
    seen = set(); dedup = []
    for v in out:
        k = (v["target"], v["violation_type"], v["sim_time"])
        if k in seen:
            continue
        seen.add(k); dedup.append(v)
    return dedup


def _tol(times, tick_tol):
    if len(times) >= 2:
        return tick_tol * max(1.0, (times[1] - times[0]))
    return tick_tol * 30.0


def summarize(violations):
    from collections import Counter
    c = Counter(v["violation_type"] for v in violations)
    targets = defaultdict(set)
    for v in violations:
        targets[v["violation_type"]].add(v["target"])
    return {k: {"event_count": c[k], "unique_targets": len(targets[k])} for k in c}
