# C3 Diagnostic Result — SURVIVAL_AWARE_PRELOCK_ADMISSION (white-combat-0004-v1)

## Parent
ACE

## New episodes used
2 (C3 on S1 12301, C3 on S6 12301); ACE baselines on the same seeds reused.

## Assigned -> First Lock
| strategy | ACE | C3 |
|---|---|---|
| S1 | 53.8% | 54.1% (≈unchanged) |
| S6 | 29.6% | 38.8% (+31% rel) |

## LA-F1 share of no-lock
| strategy | ACE | C3 |
|---|---|---|
| S1 | 74% | 71% |
| S6 | 82% | 85% |

LA-F1 essentially unchanged -> the underlying "assigned but never reached lock range" is NOT removed.

## Combat
| strategy | ACE k/l CER | C3 k/l CER |
|---|---|---|
| S1 | 14/8 = 1.75 | 16/9 = 1.78 (≈) |
| S6 | 10/17 = 0.588 | 10/15 = 0.667 (slightly better) |

## Mechanism verdict
**PARTIAL / WEAK.** Lock rate up on S6 (the harder no-lock rate case), unchanged on S1; LA-F1 not reduced;
combat neutral-to-slightly-positive. The pre-lock survival admission does not clearly move the dominant
LA1-E either — consistent with LA1-E being a consequence of chasing far/lost targets, which the
allocator (not the controller) decides.

## Next bottleneck
- LA1-E (USV dies while chasing a far/lost target) is driven at the ALLOCATOR level (committing to
  far/lost tracks), not the controller. Recommended next step: revisit the allocator's target-eligibility
  (avoid committing to far, low-persistence tracks) OR sensing persistence — but with the deterministic
  step mode first, so small-sample results are trustworthy.
