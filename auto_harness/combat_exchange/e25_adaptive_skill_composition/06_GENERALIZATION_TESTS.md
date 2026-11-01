# 06 — SCENARIO-INDEPENDENCE CHECKS
- **Code inspection (VERIFIED)**: C27/C28 and `adaptive_skills` never read a scenario name/ID/route or seed;
  they use only `obs`/`tracks`/`legal`/sim-time. No `if scenario==...` branch exists.
- Scenario **Rename Test / Hidden Metadata Test / Situation Perturbation / State Handoff**: **NOT_RUN** this
  round (no code path depends on scenario identity, but the runtime rename test was not executed → honest
  status NOT_MEASURED).
- Potential state-handoff risk (UNRESOLVED): composer switches USV mode with HOLD=3; when it flips
  ACTIVE_SEARCH↔CONTACT_MAINTENANCE it does not drop locks (lock actions bypass `_move`), but the W2-2
  regression under C28 suggests CONTACT_MAINTENANCE reverting to screen during active contact hurt.
