# Simulator run-level nondeterminism (verified)

A 2-run probe (same code, same seed 4001, B3 S1, W6, minutes apart) gave:

  attempt 1: Victory, clean, usv_dead=1.0, resolution=13984s, screen=0
  attempt 2: Defeat,   clean=0, usv_dead=5.0, resolution=28713s, screen=106

The scenario-level RNG reseed added in scenario_builder.build_scenario covers Python
`random`/`np.random` used during scenario construction and (we believe) combat hit rolls,
but the run is STILL not bit-reproducible. Residual variance sources are suspected in the
long-lived sim_server process: multithreaded stepping / wall-clock timing, or a draw that
depends on process history between the reseed and combat.

## Consequences (must be stated in any report)

1. Same (code, seed, composition) does NOT imply the same episode. Each run is a draw.
2. DEV single-run "variant confirmations" (dev2.1 vs Fix G vs overlay, N=1/seed) are NOT
   reliable: differences are largely run noise, not code effect.
3. The FINAL N=10-per-setting results are draws. Stage deltas should be read as descriptive
   means with bootstrap 95% CIs, NOT as tight paired effects.
4. This mirrors how the earlier 180-episode formal opponent eval was framed (N=30 means),
   and is acknowledged as a simulator limitation rather than hidden.

## Mitigation applied
- N fixed at 10 per (scale,stage) — no追加.
- Report means + offline bootstrap CIs.
- Clean-rate reported as x/10 (count), no significance inflation.
- All three stages share the same 10 seeds, so seed-level difficulty is partially controlled.
