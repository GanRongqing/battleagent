# C3 Root-Cause / Determinism Phase — Final Report

## 1. Did deterministic mode truly reduce same-seed variance?
**PARTIAL.** The `logical_release_until` fix (already applied) removed CUMULATIVE step-boundary drift
(release targets are now t0 + n*30). But the engine still advances **continuously** (sim_server calls
`engine.update()` with no delta), so the observed sim_time = target + a wall-clock-dependent overshoot
(2-4 s, varying). Full determinism requires the `advance_until` step mode (design in `determinism/`).
Status: **DETERMINISM_IMPROVED, NOT SOLVED.**

## 2. What does LA-F1 mainly consist of?
Decomposition of the 396 no-lock assignments (W5 baseline, 0 new episodes):
- **LA1-E WHITE_DIED_BEFORE_CLOSURE = 48.2%** (6/6 strategies) -> DOMINANT; profile = far (min 102 km),
  half-lost (visibility 0.53) target; the USV dies before entering lock range.
- LA1-D GEOMETRY_OSCILLATION = 24.5% (visible, closes to ~47 km, oscillates).
- LA1-F LEGAL_LOCK_MISSED = 13.9% (entered < 40 km but no lock issued).
- LA1-A TRACK_LOST = 7.6%; others small.
Control: failing assignments are LESS visible (0.68 vs 0.96) than successful locks.

## 3. Why did C2 have lock rate up but TTFL up?
Because "never reached lock range" is not "did not close hard enough": the failing USVs are chasing
far/lost targets (LA1-E/LA1-A) or oscillating near the threshold (LA1-D). Closing harder converts some
(fewer) assignments into locks but does not shorten the time to first lock (TTFL) and can even lengthen
the assignment denominator shrinkage.

## 4. Why is "more aggressive closing" not a sufficient fix?
It cannot address LA1-E (the USV is killed while far/lost) nor LA1-D (already at ~47 km, oscillating).
These are not closure-magnitude problems.

## 5. Primary root cause?
**LA1-E — WHITE_DIED_BEFORE_CLOSURE (48.2%).** But its driver is the ALLOCATOR committing USVs to FAR,
LOW-PERSISTENCE tracks (visibility 0.53, min-distance 102 km), i.e. a **commitment-eligibility /
sensing-persistence** problem more than a controller-closure problem.
Secondary: LA1-D geometry oscillation; LA1-F legal-lock-missed.

## 6. Was C3 created?
**YES** — white-combat-0004-v1 SURVIVAL_AWARE_PRELOCK_ADMISSION (`agent_hybrid_prelock_survival.py`),
unit tests 6/6.

## 7. Did C3 help?
**PARTIAL/WEAK.** 2 diagnostic episodes:
- S1: ACE 14/8 (1.75) -> C3 16/9 (1.78); lock rate 53.8% -> 54.1% (≈).
- S6: ACE 10/17 (0.588) -> C3 10/15 (0.667); lock rate 29.6% -> 38.8% (+31% rel).
- LA-F1 share essentially unchanged (S1 74%->71%, S6 82%->85%).

## 8. Did it push the bottleneck further?
**Not clearly.** LA-F1 is not reduced, so the bottleneck did not migrate forward. The evidence points
back to the ALLOCATOR committing to far/lost targets (LA1-E) and to SENSING PERSISTENCE.

## Recommendation
1. **Fix determinism first** (`advance_until` step mode) so small-sample results are trustworthy.
2. Then revisit **allocator target-eligibility** (do not commit to far, low-persistence tracks) or
   **sensing persistence** — NOT another controller-closure heuristic.
