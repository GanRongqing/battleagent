# STATE_LOGGER_DESIGN

## Purpose
Capture per-decision legal snapshots so the W6/W5 allocator can be replayed offline on
identical inputs — decoupling "allocator function determinism" from "live-sim trajectory
repeatability" (the two questions of this round).

## Where it lives
`agent_hybrid_w6.py` — `_log_alloc_state(...)`, called once per allocator decision point
(after `alloc` is finalised, before any controller/side effect). Enabled only when
`W6_ALLOC_LOG=1`; path from `ALLOC_STATES_PATH` (default `/tmp/opencode/allocator_states.jsonl`).

## Decision-neutrality
- Writes one JSON line per decision. No simulator write, no controller call, no timing gate,
  no allocator-side read of the log.
- The logged values are taken from the SAME objects the allocator used; nothing is mutated.

## Snapshot content (legal only)
- meta: episode tag, scenario, seed, sim_time, decision_index, mission
- friendly platforms: id, position, alive, locking/frozen flags, locking_unit, battery
- usv_map (existing commitments), fleet counts
- enemy tracks (BELIEF): position, velocity, heading, last_seen, confidence, point_confidence,
  maneuver_score, uncertainty_radius, is_ship, assigned set, engaged, pred_error tail
- intent whitelist (fields consumed by ThreatAllocator / allocator_centric)
- base_alloc (live W5 allocator output) and final alloc

Explicitly NOT stored: any ground-truth / hidden waypoint / B3 internals / future truth —
the running W6 code never receives them, so the snapshot cannot contain them.

## Replay input construction
`replay_analysis.py` rebuilds `EnemyTrack` (same class as live) from the snapshot, plus usv
list, usv_map, and intent (`SimpleNamespace`), then calls the real allocator modules.

## Why this supports the round
- Same-state determinism: replay the same variant 10x on the same state → must be identical.
- Component activation / decision-change: run A→F on the same state, diff signatures.
- Hidden-truth counterfactual: output depends only on stored belief.
