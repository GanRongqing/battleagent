# 10 — OFFLINE VERIFIER DESIGN
`target_lifecycle_verifier.py` (read-only, never in the agent loop):
- Inputs: `active_series{target:[(sim_time,has_position)]}`, `kill_events{target:[t]}`,
  `revive_events{target:[t]}` (optional).
- Checks: timestamp monotonicity (raw order); `ACTIVE_AFTER_KILL` (FD); `KILL_NO_REOBSERVATION`
  (unverified); `REVIVE_WITHOUT_ACTIVE` (false revival); `TRUE_REVIVAL` info.
- Deduplicates `(target, violation_type, sim_time)` so repeated per-step logs = ONE event.
- Emits: target_id, sim_time, previous_state, input_event, evidence_source, next_state, violation_type,
  reason.
- No engine-truth access (unit tests forbid truth tokens). Does not control the agent.
