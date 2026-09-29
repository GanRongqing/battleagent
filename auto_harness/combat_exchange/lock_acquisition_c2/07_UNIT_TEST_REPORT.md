# 07 — Unit Test Report (C2)

`test_lock_geometry.py` — 5/5 PASS:
- test_1: pre-lock, target beyond LOCK_RANGE -> C2 closes toward target.
- test_2: pre-lock, target at 35 km but lock NOT legal -> C2 closes (no band standoff).
- test_3: within LOCK_RANGE + legal lock -> LOCK action preserved (not overridden by move).
- test_6: already-locked target -> pre-lock rule does not apply (post-lock behaviour kept).
- test_8: variable cardinality 3/5/10/15/20 friendly USVs.
