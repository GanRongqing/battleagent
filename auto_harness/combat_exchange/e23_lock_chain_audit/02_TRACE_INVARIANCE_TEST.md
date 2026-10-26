# 02 — TRACE INVARIANCE TEST (TRACE ON vs OFF)
Same C19 W2-1, seed 43001, `LOCK_TRACE` ON (`e23_c19_trace`) vs the existing OFF run (`e21_w21_c19`):
| metric | OFF | ON |
|---|---|---|
| traj signature | c2b1e6ec90ca | **c2b1e6ec90ca** |
| Black_Killed / White_Lost | 4/20 | 4/20 |
| per-USV death times | identical | identical |
**INVARIANT = TRUE (VERIFIED).** Trace is default-off (no-op without `LOCK_TRACE`), writes read-only
JSONL in the exact state-transition points, never touches RNG/order/Agent input.
