# 10 — FRESH-RNG DESIGN (E9_FRESH_RNG; only if safe)
Known: after the determinism fix, the lock hit is a seed-independent `_stable_rand(unit,enemy,time)` hash,
so nominal seeds give identical combat trajectories.

Design (separate branch, isolated epoch):
1. Seed an episode RNG from the engine seed: `seed_rng = random.Random(seed)`.
2. Draw the hit order-independently: `random.Random(f"{seed}|{X}|{E}|{tick}").random() > 0.2`.
   - preserves the 80% rate, the 300 s rule, and all combat rules;
   - makes outcomes a deterministic function of the engine seed;
   - does not expose the RNG to the agent.
3. Verify: same seed → identical trajectory; different seeds (44001..44003) → distinct trajectories and
   distinct draw sequences (controlled test). If no distinct outcomes appear after real stochastic events,
   report `FRESH_RNG_BLOCKED` rather than claiming independence.
4. Freeze the engine build hash; run a paired panel (2 candidates × 4 scenarios × 3 seeds) in a new epoch.
5. Never mix with E9 deterministic stats; never overwrite E7–E9 evidence.
Status: **NOT executed this round** unless the deterministic benchmark completes and the change is safe.
