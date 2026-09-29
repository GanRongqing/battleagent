# Framework Upgrade Report

## Part A — Mechanism-Level Version Memory

1. **Offline code candidate is a version-evolution source?** **YES** (implementation-level).
2. **Avoid eyeballing whole files?** Each version ships CODE_DIFF.patch (unified diff) +
   SEMANTIC_DIFF.md (mechanism-level). Tools: `build_semantic_diff.py`, `compare_versions.py`.
3. **Code diff vs mechanism experience?** Code diff = text hunks; mechanism experience = the
   MECHANISM_CARD (failure -> root cause -> mechanism -> applicability -> evidence -> outcome ->
   confidence -> limitations). Stored separately.
4. **Parent-child lineage?** `VERSION_LINEAGE.md` + `parent_id`/`parent_sha256` in each card/manifest.
5. **Interface change detection?** `VERSION_MANIFEST.interface_changes` (explicit; `[]` = none).
6. **ACE experience structured?** `cards/ACE/MECHANISM_CARD.json` (conditional reserve release; evidence;
   DEV_SUPPORTED / FRESH_UNCONFIRMED; Fresh-invalid limitation).
7. **C2 negative experience structured?** `cards/C2/MECHANISM_CARD.json` (lesson: "never reached lock
   range" != "close more aggressively"; status INCONCLUSIVE).

## Part B — Pluggable Predictor Library

8. **Prediction abstracted to a pluggable interface?** **YES** (`MotionPredictor.predict`).
9. **Predictors?** ConstantVelocity, ConstantTurn, RecentVelocity (+ future plugins).
10. **Online model selection?** **YES** (`PredictorManager.select`, min recent EMA error, with fallback).
11. **Uncertainty interface?** **YES** (`Prediction.uncertainty_radius`, grows with horizon/age/error).
12. **CBR?** **EXTENSION_POINT_ONLY** (`prediction/cbr/base.py`).
13. **Streaming learner?** **EXTENSION_POINT_ONLY** (documented prior; `PREDICTOR_EVOLUTION.md`).
14. **LLM-generated predictor?** **FUTURE OFFLINE EXTENSION** (documented; not implemented).
15. **W5 / ACE / C2 runtime behaviour modified?** **NO** (sha-verified in `test_version_memory.py:A9`).

## Modes
- Predictor library: default `PREDICTOR_LIBRARY_ACTIVE=false`, `PREDICTOR_SHADOW_MODE=true` (shadow-only).
- Version memory: sidecar only; not imported by any agent.

## Tests
- Part A: `test_version_memory.py` 9/9 PASS.
- Part B: `test_predictors.py` 10/10 PASS (synthetic tracks T1-T8 + selector + no-hidden-truth interface).

## Extension points explicitly NOT implemented
CBR retrieval, streaming residual learning, LLM predictor generation.
