# 08 — RUNTIME & RESOURCES
Measured: per-episode wall time (from runner console):
L1 525.7 s, L2 850.5 s, L3 1463.4 s, L4 739.2 s, L5 930.8 s, L2_s2 881.7 s, L5_s2 1058.3 s.
- First attempt of L3 run concurrently with L5 died mid-run (no result; logs showed actions flowing then process
  gone; memory was ample ~457 GiB free) → observed **concurrency/resource fragility** at 120-platform scale.
  The **solo re-run succeeded** (30/6, Victory). Failed attempt not counted in CER.
- API: one post-result `GET /stop` read timeout on L3 (after the official result) → does not affect the result.
- Peak memory / CPU / P95 step time: **NOT_MEASURED** (no direct instrumentation); not fabricated.
