# C3 Design — SURVIVAL_AWARE_PRELOCK_ADMISSION (white-combat-0004-v1)

- parent: ACE (white-combat-0002-v1)
- mechanism (ONE): pre-lock survival admission

## Root-cause link
LA-F1 decomposes to **LA1-E WHITE_DIED_BEFORE_CLOSURE = 48.2%** (6/6 strategies): the assigned USV is
committed to a FAR, HALF-LOST target (min-distance ~102 km, visibility 0.53), closes without reaching
lock range, and is killed while exposed. Secondary: LA1-D oscillation (24.5%), LA1-F legal-lock-missed
(13.9%).

## Rule
For a USV that is assigned but NOT yet locking (pre-lock), if ALL of:
  1. EXPOSED: `is_locked` or `locked_attacker`, AND
  2. TARGET LOST: the current target is not currently visible, AND
  3. FAR FROM SUPPORT: nearest friendly USV > 50 km,
then DISENGAGE toward the nearest friendly USV instead of continuing the exposed, low-return approach.

## Not changed
Allocator/ACE reserve logic, TrackManager, detection, radar, lock range, weapon, Black, scenario, judge.
Only the pre-lock move action is overridden. Post-lock behaviour unchanged. No hidden truth.

## Why not C2-style aggressive closing
C2 (closing harder) could not help LA1-E (the USV dies while chasing a far/lost target) nor LA1-D (the
USV is already at ~47 km, oscillating) — consistent with C2's mixed result.
