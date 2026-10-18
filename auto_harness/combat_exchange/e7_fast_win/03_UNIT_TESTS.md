# 03 — UNIT TESTS
`test_lifecycle_handoff_v1.py` — **10/10 PASS**:
1 OFF no revive; 2 ON revives and clears BOTH stores; 3 legacy OBS_TI_REVIVE leaves `_KILLED` stale
(documents the pre-E7 defect); 4 bearing-only never revives (no position); 5 no CONFIRMED_DEAD;
6 episode isolation; 7 idempotent (no duplicate transition); 8 no truth tokens; 9 flag-off equivalence;
10 handoff overrides legacy.
Regressions: E6 16/16, E5 verifier 12/12, observation integrity 7/7.
