# 02 — E2 SEED INDEPENDENCE GATE

## Plumbing (verified)
Chain: `run_e2_eval.py` writes `/tmp/opencode/seed_w0.txt` → engine `base_server` launched with
`RW_SEED_FILE=/tmp/opencode/seed_w0.txt` → `adaptation._seed_rng()` reads it → `random.seed(seed+1009)`,
`np.random.seed(seed+7)`. Live check: base_server process env `RW_SEED_FILE=/tmp/opencode/seed_w0.txt`.

## Nominal -> actual engine seed
| Nominal Seed | Engine reads (seed_w0.txt at run time) |
|---|---|
| 43001 | 43001 |
| 43002 | 43002 |
| 43003 | 43003 |
| 43004 | 43004 |
| 43005 | 43005 |
(recorded per episode in `04_E2_EPISODES.csv` column `Actual_Engine_Seed`, read back from the seed file.)

## Same-seed repeatability
`run_c7_eval.py --agent expand --strats W2-1 --seeds 43001 --runs 2 --det`:
- `[DET] W2-1 seed43001 identical=True` (per-macro-step state hashes identical).
- Both runs' game logs share trajectory hash `6e69d6a577b4d7f3`.
- terminal/result/kills/losses identical.
=> PASS.

## Different-seed independence (controlled engine-RNG test)
Driving `adaptation._seed_rng()` exactly:
| seed | python draws (first 3) | numpy draw #1 |
|---|---|---|
| 43001 | 0.630841, 0.276229, 0.740998 | 0.899008 |
| 43002 | 0.183091, 0.257470, 0.084974 | 0.558503 |
| 43003 | 0.432775, 0.919351, 0.019247 | 0.870070 |
Distinct draw sequences; repeated 43001 reproduces. => RNG initialization is seed-dependent.
(Outcome identity is NOT used as the test: e.g. W2-1 is seed-insensitive in outcome.)

## Gate result
SEED_GATE = **PASS** (plumbing wired + same-seed deterministic + different-seed RNG init independent).
Note: 43001–43005 here is a fixed engineering-confirmation panel, not an unseen held-out test.
