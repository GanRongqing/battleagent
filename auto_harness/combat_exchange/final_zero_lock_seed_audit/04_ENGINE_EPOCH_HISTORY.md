# 04 — ENGINE EPOCH HISTORY
- **E0 ORIGINAL**: pre-determinism. `locker.py` used the shared `random.random()`; same-seed runs
  diverged (mirror-unit freeze tie). W2-1 had 7/20 own-lock.
- **E1 POST_DETERMINISM_FIX**: `locker.py:106` replaced the shared draw with an order-independent
  deterministic `_stable_rand(...)` (commit 64eead8) + `judge_system` order fix + `PYTHONHASHSEED=0`.
  Same-seed bit-identical. Combat values changed → ACE/C7 re-baselined. **Engine seed fixed**
  (`seed_det.txt`=11001; nominal seeds inert) → this is where the C7 20+20 evaluation lives.
- **E2 POST_SEED_PLUMBING_FIX** (this audit): `svc.sh` RW_SEED_FILE now points at `seed_w0.txt`, the file
  the evaluation runners write, so the nominal seed reaches `adaptation._seed_rng()`. New epoch required;
  E1 CSVs are preserved unchanged as historical evidence.
- **E2 verification (this audit)**: 43001 x2 identical (traj 6e69d6a577b4d7f3); 43002 outcome-identical
  (W2-1 seed-insensitive); engine RNG init proven seed-dependent by controlled test (02_).
No change to RNG distribution, hit probability, lock probability, targeting or physics.
