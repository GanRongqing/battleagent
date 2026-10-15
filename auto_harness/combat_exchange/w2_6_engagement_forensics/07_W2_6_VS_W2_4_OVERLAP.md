# 07 — W2-6 vs W2-4 CONCURRENT-LOCK OVERLAP (seed 43001)

| case | max conc | mean conc | unit-lock-time(s) | t(C>=1) | t(C>=2) | t(C>=4) | t(C>=6) | sustained>=300s runs |
|---|---|---|---|---|---|---|---|---|
| W2-6_ACE | 4 | 0.21 | 6930 | 3780 | 1980 | 360 | 0 | 16 |
| W2-6_C10 | 4 | 0.25 | 8550 | 4590 | 2190 | 570 | 0 | 20 |
| W2-4_ACE | 9 | 0.22 | 9420 | 3000 | 2340 | 960 | 480 | 26 |

`C(t)` = #alive White USVs with `is_locking=True` at step t (30 s).
