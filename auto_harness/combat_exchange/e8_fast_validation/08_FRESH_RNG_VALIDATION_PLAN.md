# 08 — FRESH RNG VALIDATION PLAN (next phase; NOT executed here)
Problem: post determinism-fix, the Locker hit is a seed-independent hash (`_stable_rand`), so nominal
seeds do not give independent combat realisations (W2-6 identical across 43001–43005).

Plan (separate branch/worktree, do NOT touch E7/E8 evidence):
1. **Branch** `experiment/fresh-rng-validation`.
2. **Make the hit seed-dependent** while keeping reproducibility: seed a per-episode RNG from the engine
   seed and draw the hit from it (order-independent per (unit, enemy, tick)), e.g.
   `random.Random(f"{seed}|{X}|{E}|{tick}").random()`. Do not change the 80% rate or the 300 s rule.
3. **Verify same-seed reproducibility**: two runs of the same seed → identical trajectory hash.
4. **Verify different-seed independence**: seeds 44001/44002/44003 → ≥2 distinct trajectories and
   different RNG draw sequences (controlled test), not merely different kills.
5. **Freeze the candidate** (ACE + `LIFECYCLE_HANDOFF_V1=1`) at a recorded SHA.
6. **New epoch E9**: paired ACE+OFF vs ACE+HANDOFF across W2-6/W2-4/W2-2 × N fresh seeds.
7. **Report** per-seed W/L, mean/median CER, variance, win rate, failure cases; never pool across epochs.
8. **Protect evidence**: separate run-ids/dirs; E7/E8 unchanged; no seed cherry-picking.
Promotion to GLOBAL_DEFAULT is out of scope for E8 and requires E9 results + human review.
