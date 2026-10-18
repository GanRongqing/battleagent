# 04 — C10 INCREMENTAL VALUE
Runs (C10 + `LIFECYCLE_HANDOFF_V1=1`):
- W2-6 C10: 12/7 = 1.714 (ACE+E7: 14/13 = 1.077)
- W2-4 C10: 12/7 = 1.714 (ACE+E7: 12/5 = 2.400)

**VALIDITY FAILURE**: the two runs produced **byte-identical enemy states** (verified at steps
200/600/1200: same names + positions), i.e. the same Black route was simulated for both W2-6 and W2-4,
despite the agent requesting the correct `script_name` for each. This is a scenario-separation failure in
this multi-job parallel invocation, not a tactical result.

Therefore:
- Action differences: the only difference is the agent label (both ran the same scenario).
- Trajectory differences: NONE (identical).
- Mechanism triggers: cannot be attributed (same scenario).
- Control regression: cannot be assessed.

`C10_INCREMENTAL_EFFECT = INCONCLUSIVE` (invalid pair; do NOT use these numbers for promotion).
Re-running the pair as two **separate single-job invocations** (the E7 method that produced correct,
distinct scenarios) is required before any C10 judgement.
