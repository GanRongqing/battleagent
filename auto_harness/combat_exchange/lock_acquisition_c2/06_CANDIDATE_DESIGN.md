# 06 — C2 Candidate Design

- policy_id: white-combat-0003-v1
- parent: ACE (white-combat-0002-v1)
- mechanism: LOCK_FIRST_APPROACH (single mechanism)
- file: agent_hybrid_lock_geometry.py

## Root-cause link
LA-F1 NEVER_CLOSED_TO_LOCK_RANGE = 70.7% of no-lock (6/6 strategies). W5/ACE's `USVController` closes
toward the target when `dist >= LOCK_RANGE`, but for a **stale/lost** target (`not t.is_visible`) it
performs a 34 km **standoff** (converge-to-own-radar) instead of continuing to close, so the assignment
ends without reaching LOCK_RANGE. A secondary case enters < LOCK_RANGE but with no legal lock and then
holds the standoff band.

## Change (minimal)
In `LockFirstUSVController.step`, AFTER `super().step()`:
- Track which targets each USV has ever locked (`self._locked`).
- For any USV whose action is an ordinary `move` and whose current target is **pre-lock** (never locked)
  with a known predicted position: replace the action with a direct **close** toward the target's
  predicted position (`bearing_to(pos, tpos)`).
- Never override a `lock` action; POST-LOCK USVs keep the original W5/ACE standoff behaviour.

## Not changed
Allocator/ACE reserve release, TrackManager, detection, radar, lock range, weapon, Black, scenario,
judge, terminal condition. Uses only legal observation + TrackManager belief + own state + legal actions.
No hidden truth.

## Expected effect
Assigned -> First Lock conversion up; median TTFL down; assigned-but-never-lock down; legal-lock miss
not increased. Kill/CER are secondary (this phase gates on the transition).
