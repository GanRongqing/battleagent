# 02 — SEED INDEPENDENCE TEST (post-fix, epoch E2)

## Plumbing fix applied
`/tmp/opencode/svc.sh` `RW_SEED_FILE` -> `/tmp/opencode/seed_w0.txt` (the file the evaluation runners write).
Verified live: `base_server` process env `RW_SEED_FILE=/tmp/opencode/seed_w0.txt`.

## Same seed — determinism (independent processes)
`run_c7_eval.py --agent expand --strats W2-1 --seeds 43001 --runs 2 --det`:
- `[DET] W2-1 seed43001 identical=True` (per-macro-step state hashes identical).
- run A game_1_20261012_021152.json and run B game_2_20261012_023150.json have identical trajectory
  hash `6e69d6a577b4d7f3` (991 steps, Result.Defeat).

## Different seed — RNG initialization independence (controlled engine-RNG test)
Driving the exact engine path `adaptation._seed_rng()` (reads RW_SEED_FILE; `random.seed(seed+1009)`,
`np.random.seed(seed+7)`):
| seed | first 3 python draws | first numpy draw |
|---|---|---|
| 43001 | 0.630841, 0.276229, 0.740998 | 0.899008 |
| 43002 | 0.183091, 0.257470, 0.084974 | 0.558503 |
| 43003 | 0.432775, 0.919351, 0.019247 | 0.870070 |
- same seed 43001 repeated -> identical draws (reproducible).
- 43001 vs 43002 -> different draw sequence.
=> different seeds produce **independent RNG initialization**.

## Trajectory note (seed-insensitivity of W2-1)
Post-fix W2-1 at seed 43001 and 43002 both yield CER 0.0 / 0 own-lock / first death 07:32:30, with the
**same** trajectory hash as the pre-fix (seed 11001) run. W2-1 is **seed-insensitive**: its outcome is
set by deterministic engagement geometry (no White unit ever reaches lock range), not by the stochastic
hit RNG. Per the spec this is expected ("different seed does not have to change the outcome"); the
positive RNG-independence evidence is the controlled test above, not the W2-1 kills/losses.

## Verdict
- same-seed deterministic = YES
- different-seed RNG independence = YES (controlled engine-RNG test + plumbing fix verified)
- new evaluation epoch required = YES (E2 POST_SEED_PLUMBING_FIX)
