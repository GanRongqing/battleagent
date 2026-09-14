# White Harness W6 — Final Delivery Report

## 1. Overview
W6 is the completed second-generation adaptive White Harness: an anti-evasion / evidence
decision layer layered on the frozen W5 execution base. This report finalizes W6 (deliverable =
`W6_MODE=dev3`), records the full development history and both positive and negative results,
and fixes the relationship to W5 and W7.

## 2. Architecture
Observation(/status + /legal_actions) -> TrackManager/belief (EnemyTrack) -> Prediction
(ShortHorizonPredictor) / Risk (BreakthroughRiskEstimator) / Pursuit cost -> W6 Allocator
(WHO/TASK/TARGET: allocator overlay + optional commitment state FREE/SOFT/HARD/RESERVE) ->
Assignment -> LEGACY W5 USVController/UAVManager (HOW: navigation/standoff/lock/engage/
reposition) -> ActionSafety -> simulator. W6 never writes execution geometry.

## 3. Difference from W5
W5 = deterministic baseline (allocator/controllers). W6 adds prediction/risk/breakthrough/
handoff/reserve information at the allocation seam, plus per-decision logging, same-state
replay, and commitment-state abstraction (dev4). Execution semantics remain W5.

## 4. Development history
dev1 (predictive intercept + standoff geometry; regression), dev2 (full W6 with predictive
waypoint override -> attrition regression), dev3 (allocator/execution decoupling; overlay only),
dev4 (commitment pools + elastic reserve), dev4.1 (FREE->imminent ETA-ratio -> falsified),
dev4.2 (capacity-deficit/deadline/coverage -> falsified), plus soft-rebalance/persistence
shadow audits.

## 5. Major positive engineering results
allocator/execution decoupling (execution override = 0, legacy controller reused and verified
by T21-T26/T36 etc.); fair-play + hidden-truth + same-state determinism PASS; commitment-state
abstraction; 2035-state replay dataset and audit tooling; RNG reproducibility control.

## 6. Negative / inconclusive findings (kept honestly)
- dev2 predictive-waypoint/standoff execution override caused attrition collapse.
- FREE reinforcement falsified under two independent gates (relative ETA; breakthrough deadline).
- SOFT rebalancing: large offline static opportunity but transient live; persistence P300/600/1200
  did not generalize to new DEV seeds (post600 ~0 on 4004-4006).
- No stable clean-win improvement over W5 observed (W5 remains the stronger deterministic
  performance baseline).

## 7. Final selected runtime
W6_MODE=dev3 (stable; decoupled; legacy execution). agent_hybrid_w6.py.
Manifest: W6_FINAL_MANIFEST.json.

## 8-10. Fair play / Determinism / Variable cardinality
All PASS (static leakage audits, same-state replay deterministic 100x10, hidden-truth
counterfactual PASS, variable-cardinality tests PASS).

## 11. Performance status
Honest: W6 mechanisms fire (prediction/risk active ~74%) but assignment-level actionability is
low and no clean-win improvement over W5 was established. W6 is delivered as an
adaptive/evidence-driven harness generation with known limitations, not as a win-rate upgrade.

## 12. Known limitations
See manifest; core ones: low assignment-level actionability; falsified FREE/SOFT/persistence
rebalancing; no robust performance gain; dev4.1/4.2 triggers excluded.

## 13. Quick start
See W6_FINAL_QUICKSTART.md (W6_ANTI_EVASION=1 W6_MODE=dev3).

## 14. Relationship to W7
W6 is COMPLETE and frozen as history. W7 (w7_performance_push) is the separate
performance-first next generation, developed on the W5 base, and is NOT folded into W6.
Strategy registry (strategy_library) treats white-w5 (frozen), white-w6 (completed) and any
W7 candidates (experimental) as distinct entries.
