# 05 — RANDOMNESS & REPRODUCIBILITY AUDIT
- The 16 Black routes are **deterministic** (fixed waypoints, fixed speeds). The engine combat roll uses
  `locker._stable_rand(attacker, target, int(time))` — a **seed-independent** hash (E12/E28 verified: nominal seeds
  43001/43002 produce identical trajectories). Engine RNG (`_seed_rng` from RW_SEED_FILE) seeds cosmetic draws only.
- Therefore: same config+seed ⇒ identical episode; **different seeds do NOT create independent random samples**
  for these scenarios. VERIFIED by construction + E28's identical-seed result. (Explicit per-scenario seed-repeat
  runs for F02/F08/F10 were not re-executed this round → NOT_MEASURED for the specific reruns, but the
  determinism is established and E31's TRACE-ON/OFF bit-identity confirms no residual nondeterminism.)
- Consequence: all E35/E34/E33 results are single deterministic samples per (config, seed); no CIs or
  independent-sample counts are claimed.
