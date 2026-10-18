# 13 — FINAL REPORT (E6)
ROOT_CAUSE_CONFIRMED = YES
- kill_detect's inferential heuristics (engaged_missing on a black-kill delta; corpse stationary test)
  mark LIVE targets dead; `killed_names` (and the duplicate global `_KILLED`) then suppress their tracks
  and remove them from allocation/lock candidates.
- Traced W2-4: false kill usv13 @7800 -> (ON) revive @7830 -> track restored -> assignment/action diverge
  @8160 -> outcome 12/6 -> 9/20.

STATE_CONTRACT_VALIDATED = YES (lifecycle states, provenance, dedupe, no truth, tests 16/16).

MINIMAL_PATCH_VALIDATED = YES (bookkeeping-only, flag-gated, behaviour-neutral, OFF-equivalent).
COMBAT_BENEFIT_VALIDATED = **NOT_YET** (the behaviour-changing restore is not deployed).

## Final decision: `PATCH_BLOCKED_BY_INTERFACE_SEMANTICS`
The state/lifecycle repair is correct and safely shippable as *bookkeeping*, but the effective fix
(restoring live-but-falsely-killed targets) cannot be safely enabled because the allocator/controller
interface treats a restored live target as a normal engagement candidate, collapsing W2-4 (2.000->0.450).
A downstream engagement-semantics change (e.g., "restored" vs "new priority" distinction) is required
before any fresh combat evaluation.

## Git / scope
- Branch `experiment/e6-lifecycle-state-integrity`.
- ACE/C10/C11/engine/Black unchanged; OBS_TI_REVIVE default 0; TARGET_LIFECYCLE_V2 default 0.
- No C12; no full epoch; E4/E5 logs not overwritten.
