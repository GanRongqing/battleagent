# BUG_FIX_LOG

## Bug 1 — dev3/iso metrics contamination by ignored dev2 allocation

- **File:** `anti_evasion/w6_harness.py`, `agent_hybrid_w6.py`
- **Symptom:** in dev3 / prediction_only / isolation runs the agent called
  `W6DecisionCore.step()` only to obtain features, but `step()` internally also ran the dev2
  `w6_allocation` (collapse + handoff bookkeeping). Its return value was ignored (the real
  allocation comes from `allocator_centric`), yet its metric side effects (e.g. `handoff_count`,
  `handoff_evaluations`) still incremented — making `handoff_count` non-zero in prediction-only
  runs even though no assignment handoff was applied.
- **Fix:** added `W6DecisionCore.features()` which computes corridors / intercept-plans / risks
  / criticalities / screen-demand only (no allocation). `agent_hybrid_w6.py` now calls
  `features()` whenever `EXECUTION_OVERRIDE` is false (dev3 / prediction_only / isolation) and
  `step()` only in dev2 mode.
- **Behavioural impact:** NONE on the actual allocation (allocator_centric already recomputed
  the assignment independently); pure metrics-hygiene. Unit suites re-run green
  (`test_w6_units.py` 34/34, `test_w6_dev3_units.py` 15/15).
- **Rerun:** not required for decision purposes (assignment behaviour unchanged); a future
  confirmation run of variant F with clean counters is optional.
