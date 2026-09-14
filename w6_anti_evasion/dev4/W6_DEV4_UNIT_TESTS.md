# W6-dev4 Unit Tests (T27-T36) — test_w6_dev4_units.py
T27 FREE | T28 SOFT | T29 HARD lock | T30 HARD frozen | T31 HARD not releasable |
T32 SOFT releasable (covered old target) | T33 reserve release on risk clear |
T34 reserve demand on uncovered critical | T35 endgame reserve 0 | T36 no execution
override under dev4. **Result: 15/15 PASS.** Regressions: test_w6_units 34/34,
test_w6_dev3_units 15/15 (dev4 is feature-gated, default dev2 unaffected).
