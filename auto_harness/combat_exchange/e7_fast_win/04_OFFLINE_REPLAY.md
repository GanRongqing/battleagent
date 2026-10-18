# 04 — OFFLINE REPLAY (Gate B)
Using E6 W2-4 ON trace (real log):
- step 260: `kill_detect` false-death `usv13` (recorded in trace `kill_events_this_step`).
- step 261: `killed_names` becomes empty (revive) and the track is restored; **but** `_KILLED` still
  contains `usv13` (code-confirmed, l.2821 unconditional update) → inconsistent handoff.
- step 272: assignment/action divergence downstream (action_hash 584b19fa6542 -> 9f006f411790).
- E6 ON run: 139 revive events; verifier: 209 `ACTIVE_AFTER_KILL` unit-steps.
With HANDOFF=1 the same observation would clear `_KILLED` too, yielding a consistent `OBSERVED_ACTIVE`
handoff (unit test 2). Success criterion = interface consistency + explainable transitions; not
"actions unchanged".
