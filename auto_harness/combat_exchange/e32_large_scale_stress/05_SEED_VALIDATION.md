# 05 — SEED VALIDATION
- Requested seed == actual engine seed for all runs (43001 / 73121).
- Black movement is `random_waypoint` seeded from `RW_SEED_FILE` (scenario_builder reseeds np/random via rw_seed),
  so the seed genuinely changes Black paths.
- Trajectory-hash comparison (White USV position/alive sequence):
  - L2: seed 43001 `e64a1ac3f225ca67` vs seed 73121 `73d58afa005504cb` → **DIFFERENT**
  - L5: seed 43001 `4af09478539634ef` vs seed 73121 `ae39fd2a5b090f6f` → **DIFFERENT**
=> seed 73121 produces genuinely different episodes → valid independent re-checks (not nominal-only).
Caveat: `first_detection/first_lock/first_kill` happen to coincide across scales/seeds (≈3390/7380/8280 s) due to
the identical initial deployment line and approach timing; this does NOT mean identical trajectories (hashes differ).
