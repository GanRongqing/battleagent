# W6 SOFT Rebalancing Counterfactual Audit

## 1. Motivation
FREE reinforcement was falsified twice (dev4.1 ratio gate 0/2035; dev4.2 breakthrough-deadline
0/2035). Resource density is in the SOFT pool; this audit asks whether a coverage-safe,
commitment-aware positive reassignment subset exists in the 2035 legal states.

## 2. SOFT semantics
Alive, committed target, no lock/frozen (INTERCEPTING/approaching). Protections used:
near-lock (dist<LOCK_RANGE), unique feasible interceptor, coverage (leaving must not strip
another HIGH corridor of its only in-time candidate).

## 3-4. Dataset + census (2035 states)
states with SOFT>0: 1504 | mean SOFT/state 4.96, median 4, p25 0, p75 10, p90 10 |
frac states SOFT>=2: 72% | total SOFT instances 10099.

## 5. Counterfactual variants
| variant | eligible (SOFT instances) | change states | near-lock abandon | unique abandon | coverage damage |
|---|---:|---:|---:|---:|---:|
| A BASE (FREE only) | 0 | 0 | 0 | 0 | 0 |
| B ALL_SOFT | 9386 | 9386 | 1205 | 26 | 26 |
| C PROTECTED | 8166 | 8166 | 0 | 0 | 0 |
| D COMMITMENT_AWARE | 5876 | 5876 | 0 | 0 | 0 |

## 6-8. Filters / funnel
10099 SOFT -> has legal alternative 9386 -> not near-lock 8181 -> (not-unique/coverage-safe ~9360) ->
D (multi-criteria dominance) 5876. Classes: STRONG_POSITIVE 5876, WEAK_POSITIVE 1922,
AMBIGUOUS 368, NEGATIVE 0. D gates: near-lock violations 0, unique abandon 0, coverage damage 0.

## 9-11. Interpretation (honest caveats)
- Near-lock abandonment in B is 1205/9386 (~13%): naive all-SOFT would abandon near-lock
  interceptors. After C protection these all drop to 0.
- D's "strong" set (5876) is an UPPER BOUND under a permissive multi-criteria evidence rule
  (alt risk-tier improvement is dominant; eta improvement 5562, alt>=HIGH 8155 of candidates).
  It is NOT the hoped sparse 5-15%; that is likely because W5 leaves many LOW/medium current
  targets with a single movable interceptor while HIGH alternatives exist. Per round rule, no
  rule tuning was applied to force sparsity.
- Mechanism signals on candidates: risk/breakthrough-driven 1758, prediction/ETA-driven 4787,
  coverage-recovery/priority-shift 1231, eta/ranking-like 4118 (overlapping).

## 12-14. Determinism / Fair play
Pure functions over legal states; same-state deterministic (replay audits PASS earlier);
hidden-truth counterfactual PASS.

## 15. Recommended next step
CASE A-boundary: a coverage-safe, near-lock/unique-protected positive subset exists but is
large (not sparse) under the permissive evidence rule. Before any live SOFT rebalancing the
positive definition must be sharpened with live quality audit (GOOD/BAD labels at decision
level), i.e., treat 5876 as an upper bound, not as ready-to-implement triggers. Implement live
SOFT rebalancing ONLY for a minimal protected trigger (not near-lock, not unique, coverage
safe, alt HIGH/CRITICAL while current is not) and validate quality offline first.
