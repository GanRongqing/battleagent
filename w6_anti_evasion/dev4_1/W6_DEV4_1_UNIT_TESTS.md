# W6-dev4.1 Unit Tests (T37-T46) — test_w6_dev4_1_units.py  [10/10 PASS]
T37 ratio<=1.5 & below cap -> trigger YES | T38 ratio 1.8 -> NO | T39 risk<HIGH -> NO |
T40 at concentration cap -> NO | T41/42 FREE-only (SOFT/HARD untouched) | T43 legacy execution
under dev4_1 | T44 invalid/zero/missing ref ETA -> deterministic NO (no crash) |
T45 variable cardinality (per-target cap, no fleet-count branch) | T46 pure/deterministic.
Regressions: test_w6_units 34/34, test_w6_dev3_units 15/15, test_w6_dev4_units 15/15.
