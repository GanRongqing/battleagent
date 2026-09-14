# W6-dev3 Allocator-Centric Anti-Evasion — DEV report

## 1. Motivation

W6-dev2's anti-evasion *sensing* is real (mechanisms fire; exploration burden drops:
S1 89,340→57,930, S2 86,430→81,420, S3 100,370→91,206 km² in the prior three-stage runs),
but its *execution coupling* coincided with a survival collapse (S2 0/10 clean, ~9.5 mean
friendly loss). dev3 tests whether keeping anti-evasion purely at the allocator layer
(WHO/WHAT/TARGET), with the legacy W5 controller doing ALL navigation/standoff/lock/engage,
restores survival while retaining the exploration benefit.

## 2. Architectural change

WHO/WHAT/TARGET (allocation) is fully decoupled from HOW (execution). New `W6_MODE`
config ∈ {w5, dev2, dev3, prediction_only}; dev3 & prediction_only run with
`execution_override = false` → the agent never writes `_w6_intercept` and never rewrites a
controller move. Unit-verified: `w6_execution_override_actions` = 0 for dev3/prediction-only
in every diagnostic episode (dev2: 15–151/game).

## 3. Preserved mechanisms (allocator/scalar layer)

Prediction → intercept-ETA / risk / reserve scalars; breakthrough-horizon risk;
pursuit-cost-aware assignment; protected handoff (owner change only); UAV track
maintenance (legacy UAV path); adaptive defensive reserve (threat-driven, resource-relative,
endgame-aware, no fixed counts).

## 4. Removed execution overrides

Predictive waypoint (`_w6_intercept`), W6 intercept/standoff geometry, screen navigation
deploy. `AdaptiveScreenPlanner` is now a resource-demand estimator only.

## 5. Execution equivalence

Same assignment → same legacy W5 `USVController.step` output (tests T22/T25/T26; 15/15 dev3
unit tests pass; all regression suites green).

## 6–8. Diagnostic ablation (S1/S2 × B3 × 4001–4003 × W5/dev2/dev3/prediction-only)

See `W6_DEV3_ABLATION_REPORT.md` and `W6_DEV3_DIAGNOSTIC.csv`. Summary: dev3 vs dev2
friendly loss S1 5.0→3.0 (−40%), S2 10.0→8.0 (−20%); exploration benefit retained vs W5;
0 execution overrides. BUT dev3 S2 still ~8/10 USV dead → survival gate NOT met.

## 9. Decision

- DEV3 ARCHITECTURE VALID = YES (boundary holds, unit tests, 0 overrides)
- SURVIVAL COLLAPSE FIXED = PARTIAL (S1 improved; S2 not restored to W5)
- ANTI-EVASION BENEFIT RETAINED = YES (exploration < W5×B3)

NEXT: **STOP AND AUDIT ALLOCATOR** (component isolation of the allocator score: W5 →
+prediction → +breakthrough-risk → +pursuit-cost → +handoff → +reserve, one at a time,
legacy execution). Do NOT run the 3-scale DEV / freeze W6-dev3 yet. Note N=3 + run-level
noise limit confidence; diagnostic seeds 4001–4003 remain DIAGNOSTIC (5001–5010 reserved for
any future FINAL).
