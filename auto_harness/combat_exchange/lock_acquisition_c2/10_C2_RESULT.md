# C2 Lock Acquisition Diagnostic Result

## Parent
ACE (white-combat-0002-v1)

## Root Cause
LA-F1 NEVER_CLOSED_TO_LOCK_RANGE = 70.7% of no-lock assignments (6/6 strategies). Per-assignment lock
rate baseline = 71.6%.

## Candidate Change
LOCK-FIRST APPROACH: before the first lock of the current target, always close toward the target's
predicted position instead of holding the standoff band (esp. for stale/lost targets). Post-lock
behaviour unchanged. Only `USVController` pre-lock closure; allocator/sensing/detection untouched.

## New Episodes Used
4 (ACE + C2 on S1 12301; ACE + C2 on S6 12301)

## Assigned -> First Lock (per-assignment)
| strat | ACE | C2 | delta |
|---|---|---|---|
| S1 | 53.8% | 70.3% | +16.5pt (+31% rel) |
| S6 | 29.6% | 41.2% | +11.6pt (+39% rel) |

Lock rate improved on BOTH strategies. But C2 also made FEWER assignments (S1: 158->91), so part of the
gain is a smaller denominator (more selective), not purely faster locking.

## Median TTFL
| strat | ACE | C2 |
|---|---|---|
| S1 | 297.8s | 355.0s |
| S6 | 257.0s | 277.1s |

TTFL did NOT improve (slightly worse on both) — the TTFL gate (>=25% down) is NOT met.

## Assigned Never Lock
Improved (lock rate up on both).

## White Death Before Lock
NOT_MEASURED per-target (game logs lack locking_unit); no-lock deaths remain a downstream effect.

## Black Kills / White Losses / CER
| strat | ACE k/l CER | C2 k/l CER |
|---|---|---|
| S1 | 14/8 = 1.75 | 12/12 = 1.00 (worse) |
| S6 | 10/17 = 0.59 | 12/15 = 0.80 (better) |

Combat outcome is MIXED.

## Mechanism Verdict
**PARTIALLY_SUPPORTED / INCONCLUSIVE.** Directionally the lock rate rises on both strategies, but the
TTFL does not fall (the primary gate), and the assignment denominator shrank. This is NOT a clean
mechanism PASS and NOT a clean DROP.

## Next Bottleneck
SURVIVAL_GEOMETRY (exchange is ~1:1; USVs die while exposed; 81% of deaths without own lock).
