# 02 — LOCK-DURATION DEFINITIONS

Time base: 1 logged step = 1 macro-step = **30 sim-seconds** (W2-6 ACE 1118 steps ↔ 33 540 s;
`MACRO_STEP=30`). All log-derived durations are computed at 30 s resolution.

| metric | definition | unit |
|---|---|---|
| unit-lock-steps | Σ over steps of (#alive White USVs with `is_locking=True`) | steps |
| **unit-lock-time** | unit-lock-steps × 30 | sim-s |
| single continuous lock duration | for a (unit) run of consecutive `is_locking=True` steps × 30 | sim-s |
| concurrent locks C(t) | # distinct White USVs with `is_locking=True` at step t | count |
| max concurrency | max_t C(t) | count |
| lock-overlap time | Σ_t 30 | s | if C(t)≥1 |
| time with C(t)≥k | Σ_t 30 for C(t)≥k | s |
| lock interruption | an `is_locking` True→False transition (excluding death) | count |

## Re-interpretation of the old numbers 231 / 285 / 314
They are **unit-lock-steps** (Σ concurrency over steps), NOT seconds and NOT single-lock durations.
- W2-6 ACE 231 steps → **6 930 unit-lock-seconds**
- W2-6 C10 285 steps → **8 550 unit-lock-seconds**
- W2-4 ACE 314 steps → **9 420 unit-lock-seconds**

**CORRECTION to the earlier `next_positive_exchange` report**, which labelled 231/285/314 as
"lock-seconds": that label was wrong by a factor of 30. The relative ordering (W2-4 > C10 > ACE) is
unchanged, and the historical file is preserved.
