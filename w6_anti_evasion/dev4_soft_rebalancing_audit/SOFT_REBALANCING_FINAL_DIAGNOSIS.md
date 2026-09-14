# SOFT Rebalancing Final Diagnosis
DATASET states = 2035
SOFT CENSUS: states with SOFT = 1504 | mean/state = 4.96 | SOFT instances = 10099
COUNTERFACTUAL:
  B ALL_SOFT eligible 9386 changes 9386 (near-lock abandon 1205, unique 26, coverage 26)
  C PROTECTED eligible 8166 changes 8166 (near-lock 0, unique 0, coverage 0)
  D COMMITMENT_AWARE eligible 5876 changes 5876
SAFETY FILTERS (C->D): near-lock rejected 1205 (and more in C) | unique rejected 26 |
coverage rejected 26 | marginal/current-value rejected ~ (see WEAK 1922, AMBIG 368)
FINAL POSITIVE SET (upper bound): strong 5876 | weak 1922 | ambiguous 368 | negative 0
MECHANISM: risk-driven 1758 | prediction/eta-driven 4787 | coverage-recovery/priority 1231
DETERMINISM PASS | HIDDEN-TRUTH PASS
FINAL CASE = A-upper-bound (positive subset exists and is coverage/near-lock/unique safe,
but LARGE under permissive evidence; not verified high-quality at decision level)
PRIMARY FINDING = most SOFT platforms have a risk-tier-higher alternative they could safely
move to; the binding filters are near-lock (~13% of naive moves) then genuine dominance.
ONE RECOMMENDED NEXT STEP = decision-quality audit of a minimal protected trigger
(not-near-lock, not-unique, coverage-safe, alt HIGH/CRITICAL, current non-critical) before any
live SOFT rebalancing; do NOT auto-implement the large 5876 set.
