# 06 — C5 UNIT TESTS

`test_track_reacquire.py` → **11/11 PASS**
1 fresh no-op; 2 brief-stale→REACQUIRE; 3 fresh-returns exits; 4 timeout→EXPIRED; 5 uncertainty→EXPIRED;
6 predicted cannot lock; 7 predicted cannot fire; 8 all-fresh exact no-op; 9 non-assigned stale no-op;
10 ownership restored after EXPIRED; 11 predictor fallback(P0)+scoring.
