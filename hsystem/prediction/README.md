# Pluggable Predictor Library

Prediction is no longer a single hard-wired formula. It is a growing, pluggable,
online-evaluated predictor library.

```
TrackManager (unchanged)          <- W5/ACE runtime keeps using its own prediction
    |
    +-- PredictorManager (SHADOW, this package)   <- side computation only
          |-- ConstantVelocityPredictor
          |-- ConstantTurnPredictor
          |-- RecentVelocityPredictor
          |-- (future) plugin
                |
          OnlineScorer (EMA of re-observation error)
                |
          selected Prediction {position, uncertainty_radius, confidence, model_id}
```

## Default mode
- `PREDICTOR_LIBRARY_ACTIVE=false` (library does NOT take over combat control)
- `PREDICTOR_SHADOW_MODE=true` (computes + logs predictions to `shadow/`)
- **No W5/ACE/C2 behaviour change.**

## Interface
`MotionPredictor.predict(history, horizon_s) -> Prediction`.
Inputs are strictly legal: observation-derived `TrackHistory` (positions/times + estimated
velocity/heading/turn). No Black future waypoint / true position / scenario route / hidden state.

## Extension points (NOT implemented)
- `cbr/` CaseRetriever — retrieve similar historical maneuvers.
- streaming residual learner — `physics_prediction + learned_residual` (see `PREDICTOR_EVOLUTION.md`).
- LLM offline predictor evolution (see `PREDICTOR_EVOLUTION.md`).
