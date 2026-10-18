# 08 — VERSION DECISION
## Evaluation status: EVALUATION_BLOCKED
Runtime scenario identity cannot be independently verified (Defect 3). Therefore **no E8.1 result
enters the formal comparison**, and even the E7 numbers are re-classified as *plausible but
runtime-unverified*.

## Version decision
- Do **not** promote ACE+E7 or C10+E7; `GLOBAL_DEFAULT_CHANGED = NO`; all flags remain OFF by default.
- `FROZEN_VALIDATION_CANDIDATE = ACE + LIFECYCLE_HANDOFF_V1=1` is retained **nominally** from E7, but
  **must be re-validated** once runtime identity is trustworthy.
- C10 incremental value: INCONCLUSIVE. C11: DROP.

## Required before any promotion
1. Engine-level runtime identity (loaded route/blue-waypoint digest) surfaced per episode and gated.
2. Re-run the 4-way panel on unique ports with a proven-distinct signature per scenario (the runner fix
   in 03 is the first step; it still needs an engine-side identity signal to pass Defect 3).
3. Fresh-RNG epoch (independent realisations) as per E8 plan.
