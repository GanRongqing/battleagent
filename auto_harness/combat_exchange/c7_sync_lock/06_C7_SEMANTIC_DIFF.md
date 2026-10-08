# 06 — C7 SEMANTIC DIFF (vs ACE)
C7 subclasses ACE's controller and, AFTER ACE's allocation, applies ONE bounded post-process in
`SyncLockController.step`:
- For a target with **exactly 1 owner** that **has no own lock** and is **visible/actionable**, if a
  **free** (no-target) USV within `SYNC_RADIUS=150km` exists, divert that support to the target
  (form a 2-unit package).
- If the lead's predicted TTFL is > `TTFL_GAP_SLOW=60s` below the support's, **slow the lead**
  (0.5× speed, bounded) to compress arrival timing. The lead is never ordered to retreat/stop.
- Dissolve on member-lock, target loss, or `MAX_SYNC_TIME=1200s`.
Unchanged: ACE allocator/assignment, reserve/coverage, TrackManager, sensor semantics, **lock legality,
fire legality**, ActionSafety, Black, simulator. No truth/route/strategy-ID. Deterministic (sorted by
(distance, id)).
