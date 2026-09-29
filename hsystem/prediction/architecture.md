# Predictor Library — Architecture

## Components
| file | role |
|---|---|
| `prediction.py` | `Prediction` output (position, uncertainty_radius, confidence, model_id, horizon_s) |
| `base.py` | `MotionPredictor` ABC (single entry: `predict(history, horizon_s)`) |
| `history.py` | `TrackHistory` (legal, append-only samples; velocity / recent_velocity / recent_turn_rate) |
| `models/constant_velocity.py` | p(t+D)=p(t)+vD, uncertainty grows with horizon |
| `models/constant_turn.py` | circular-arc model using recent turn rate; low confidence without evidence |
| `models/recent_velocity.py` | robust recent velocity (reduces single-step noise) |
| `scoring.py` | `OnlineScorer` (EMA error per model, updated only on legal re-observation) |
| `manager.py` | `PredictorManager` (register/predict_all/select/observe; shadow default) |
| `shadow/logger.py` | logs PREDICTIONS.csv / REOBS_ERRORS.csv / MODEL_SCORES.csv |
| `cbr/base.py` | CaseRetriever extension point (interface only) |

## Selection
`select(history, horizon)`: min recent EMA error among models with >= min_evidence updates; else
fall back to `ConstantVelocityPredictor` with `selection_reason=fallback_insufficient_evidence`.

## Uncertainty
`uncertainty_radius` grows with horizon, track age and (for CT) with lower confidence.

## Safety
- Does not read hidden truth.
- Shadow-only by default; activation requires an explicit env flag (future).
- TrackManager / W5 / ACE / C2 untouched.
