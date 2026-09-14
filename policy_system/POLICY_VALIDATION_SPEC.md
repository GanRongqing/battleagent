# Validation / Novelty Spec
Layers: 1) artifact (bundle) 2) semantic (card) 3) empirical (fingerprints, core gate).
Verdicts: IDENTICAL_ARTIFACT / SEMANTIC_ONLY_DIFFERENCE / EMPIRICALLY_DUPLICATE /
EMPIRICALLY_DISTINCT / INCONCLUSIVE / INSUFFICIENT_EVIDENCE.
Multi-seed gate: need >=10 episodes/policy; empirical distance on intersection of available
standardized features; thresholds are calibration-based (policy_validation_config.json), not
theory. Weak-but-distinct policies may be admitted under evaluation_role=failure_probe.
