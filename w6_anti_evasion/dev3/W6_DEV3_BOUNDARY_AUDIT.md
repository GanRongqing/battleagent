# W6-dev3 Boundary Audit (READ-ONLY)

Audit of exactly where the current W6 (dev2 / dev2.1-restored) code modifies execution
semantics that belong to the legacy W5 controller. Basis: real code at the listed paths.
No code was changed to produce this audit.

## 1. Which W6 code directly changes USV waypoints / navigation?

Two sites in `agent_hybrid_w6.py` (the W6 `step_once`):

1. **Predictive-intercept waypoint override (lines ~115-127).**
   For every target in the W6 allocation the agent sets
   `track._w6_intercept = intercept_point` (`agent_hybrid_w6.py:117-127`), where
   `intercept_point` comes from `InterceptPlanner.plan()` (`anti_evasion/intercept_planner.py`,
   incl. standoff projection / REPOSITION_OUTWARD / LOCK_READY geometry).
   Because `EnemyTrack.predicted_position()` returns `self._w6_intercept` when set
   (`agent_hybrid_v5.py:431-432`), this overrides **the predicted position of the enemy
   track globally**, i.e. every downstream consumer that reads `predicted_position`:
   `USVController.step` approach/standoff/lock moves (`agent_hybrid_v5.py:2035, 2085, 2091,
   2099-2103`), `ThreatAllocator.threat_score` + allocation distances
   (`agent_hybrid_v5.py:1749-1791`, ~778-793), summarizer, opportunistic lock, kill detect.
   => This is a **navigation / engagement-geometry override**, not an allocation signal.

2. **Screen waypoint deployment (lines ~150-160).**
   When `AdaptiveScreenPlanner` reports a demand, the agent rewrites a free USV's `move`
   action to a concrete `screen_positions` coordinate via
   `self.usv_ctrl._move(name, pos, target_sp)` (`agent_hybrid_w6.py:155-160`).
   => This **directly emits a MOVE/waypoint command** for USVs.

## 2. Which code overrides legacy controller navigation?

Both sites above. Additionally `InterceptPlan`/`ScreenPlan` objects carry coordinates
(`intercept_point`, `screen_positions`) that are only meaningful if some executor navigates
to them; in dev2 they are turned into controller inputs (override) or direct actions.

## 3. Where does prediction enter the controller today?

Prediction enters the controller **indirectly through the track's predicted position**:
`ShortHorizonPredictor.predict()` → `PredictedCorridor`
(`anti_evasion/motion_predictor.py`) → `InterceptPlanner.plan()` →
`_w6_intercept` override → `EnemyTrack.predicted_position()` →
`USVController` standoff/approach/lock decisions. So today the W6 aim point hijacks the
legacy controller's view of *where the target is*, which changes HOW a USV steers, closes,
and locks — not merely WHO is assigned.

## 4. Which anti-evasion information can stay at the allocator layer?

The following are scalar/assignment-level signals and can feed WHO/WHAT/TARGET without
touching navigation:
- `PredictedCorridor` → per-(target, interceptor) **intercept ETA / feasibility / margin**
  (a scalar time/cost, not a waypoint).
- `BreakthroughRiskEstimator` → `breakthrough_eta`, `best_interceptor_eta`,
  `interceptor_deficit`, `risk_score` (`anti_evasion/breakthrough_risk.py`).
- `pursuit_cost.effective_value` / `intercept_advantage` / `coverage_cost` — scalar value terms.
- `HandoffEvaluator` — owner reassignment only.
- `track_criticality.criticality` — UAV maintenance priority (sensing task, not a platform
  waypoint); UAV movement already goes through `UAVManager`.
- `AdaptiveScreenPlanner` **as a resource-demand estimator only**: `screen_required_count`,
  `defensive_reserve_set`, `uncovered_corridor_count`, `critical_corridor_ids` — decisions
  about *which free USVs the offensive allocator must not grab*; never `screen_positions`.

## 5. How to fully restore W5 when W6 is disabled?

`agent_hybrid_w6.py:46-47` already delegates to `super().step_once()` when
`config.W6_ENABLED` is false, and `agent_hybrid_v5.py` contains the complete legacy stack
(USVController/UAVManager/ThreatAllocator/ActionSafety). With no `_w6_intercept` set and no
screen-deploy rewrite, W5 behavior is exactly reproduced (this is what the W5 rows in every
experiment already show).

## 6. How to make W6-dev3 = allocator enhanced + controller unchanged?

Introduce an explicit **execution-override switch** in `anti_evasion/config.py`
(`W6_EXECUTION_OVERRIDE`, default ON = dev2 behaviour). When OFF (dev3):
- Never write `_w6_intercept` (so `predicted_position` stays the legacy constant-velocity
  belief → legacy controller geometry is byte-identical to W5 for a given assignment).
- Never call the screen-deploy move rewrite.
- Keep a **W6 allocator overlay** that only changes the assignment
  `{target: [platform_ids]}` (risk/pursuit-cost reinforcement, handoff owner change,
  defensive-reserve accounting), then hands that assignment to the **same**
  `USVController.step`/`UAVManager.step` instances inherited from W5.

## 7. Verified legacy-consumer map (why execution coupling is dangerous)

`EnemyTrack.predicted_position()` is read by ~15+ sites in `agent_hybrid_v5.py`
(allocator, threat score, standoff band decisions, opportunistic lock, kill/stale logic,
summarizer, coverage). Overriding it (dev2 `_w6_intercept`) therefore changes far more than
the interceptor's aim point; it perturbs threat ranking, reserve, lock windows, and
standoff bands all at once — the likely source of the dev2 survival collapse (S2 0/10
clean, ~9.5 mean friendly loss) despite firing mechanisms.

## 8. Concrete refactor plan (dev3)

1. `anti_evasion/config.py`: add `EXECUTION_OVERRIDE` feature flag (env `W6_EXECUTION_OVERRIDE`,
   default "1"; dev3 sets "0").
2. `agent_hybrid_w6.py`: gate the `_w6_intercept` block and the screen-deploy block on the
   flag (default ON preserves dev2).
3. New allocator-centric overlay `anti_evasion/dev3_allocator.py` (or in `w6_harness`):
   base = W5 `allocate_usvs` result; overlay = risk-driven reinforcement of uncovered
   high-risk corridors with free USVs + protected handoff (owner change) + reserve
   accounting. Output stays `{target: [usv]}`.
4. When the flag is OFF: skip waypoint override + screen move; run overlay; feed same legacy
   controller. (`controller_mode = LEGACY_W5`, `execution_override = false`.)
