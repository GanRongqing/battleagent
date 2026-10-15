# 13 — SEED VARIATION ANALYSIS (E2/C10 seeds 43001–43005)

| strategy | policy | distinct trajectories / 5 seeds | K/L per seed | note |
|---|---|---|---|---|
| W2-6 | ACE | **1** (all identical, hash 279709d01258) | 10/18 | seed-insensitive |
| W2-6 | C10 | **1** (all identical, hash b177365238ca) | 11/16 | seed-insensitive |
| W2-4 | ACE | 2 (43001/02 vs 43003/04/05) | 12/6 | mildly seed-sensitive |

## Finding (important)
After the engine determinism fix (`locker.py` hit = `_stable_rand(unit,enemy,time)`), the **dominant
stochastic combat event (the lock hit) no longer depends on the engine seed**. The only remaining
seed-dependent RNG is radar/motor `np.random`, which for W2-6 does not change the outcome. Hence the 5
nominal seeds produce **identical** W2-6 trajectories → they are **not independent combat realizations**.
W2-4 varies only across two process instances (2 variants), not 5.

## Consequence
- All W2-6 mechanism numbers are effectively a **single realization** repeated; the "5-seed" evidence is
  really N≈1 for W2-6. The *shape* (own-lock 11, maxC 4, prelock 8) is stable, but it is not 5 samples.
- Cross-seed "reproduction" therefore cannot by itself prove generality. Marked NOT_MEASURED as an
  independent-sample claim.
