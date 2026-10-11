# 03 — SEED FIX SEMANTIC DIFF
Change: `/tmp/opencode/svc.sh` env `RW_SEED_FILE` : `/tmp/opencode/seed_det.txt` -> `/tmp/opencode/seed_w0.txt`.
Effect: the engine's `adaptation._seed_rng()` now reads the seed the evaluation runner writes.
NOT changed: RNG algorithms, offsets (+1009/+7), distributions, hit/lock probabilities, targeting,
lock/fire legality, physics, ACE, C7, Black, routes. No truth.
Consequence: concrete trajectories become a function of the nominal seed → results before/after this
fix are NOT mixable; the new epoch is E2 (POST_SEED_PLUMBING_FIX). Old CSVs are not overwritten.
