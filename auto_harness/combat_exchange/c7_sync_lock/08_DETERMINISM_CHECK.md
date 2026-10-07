# 08 — DETERMINISM CHECK  (GATE: PASS after deeper engine fix)

## Final result
`python run_c7_eval.py --agent sync --strats W2-1 --seeds 43001 --runs 2 --det`
-> `[DET] W2-1 seed43001 identical=True`  (per-macro-step state hashes identical, actions identical,
outcome identical). **GATE PASSED.**

## Investigation trail
1. Baseline: outcome identical, per-step hash diverged (step 945/993), mirror units usv6/usv15
   freeze swap.
2. `judge_system._judge()` raw-set iterations -> sorted by name (commit 903b7d7). Divergence persisted
   (step 929/993, usv7/usv14 swap).
3. `PYTHONHASHSEED=0` for base_server + API. Persisted.
4. **Root cause found**: `hsystem/simulation/arsenal/locker.py:106` decided the stochastic lock "hit"
   with `random.random() > 0.2`, consuming the **shared process-wide stdlib `random` stream**. The
   number/order of draws depends on the engine's per-unit traversal order, so two mirror units could
   draw in swapped order -> one freezes a macro-step earlier -> state divergence.
5. **Fix**: replace the shared-stream draw with an **order-independent deterministic** value:
   `_stable_rand(home_unit.name, emy_name, int(engine.time)) > 0.2` (stdlib `random.random()` ->
   SHA-256 based pseudo-uniform). Hit rate preserved (~80%); removed all dependence on traversal order
   / shared-RNG consumption order.
6. Re-ran gate: **PASS** (bit-identical).

## Consequence (baseline risk)
The locker hit generator now yields different specific values than before, so **combat outcomes change**
(e.g., ACE W2-1 at `seed_det=11001` -> CER 0.0 / 0 own-lock, vs the frozen baseline 0.1 / 7 own-lock).
Therefore the **frozen ACE N=5 baseline is INVALIDATED** and must be re-run under the fixed engine for a
valid paired comparison. (Also: `seed_det.txt` was overwritten during investigation; prior baseline seed
not recoverable.)

## Status
Determinism gate satisfied. C7 evaluation is pending a decision on re-baselining ACE under the fixed engine.
MD
echo done