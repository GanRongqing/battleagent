# 11 — GENERALIZATION / SCENARIO-INDEPENDENCE
- **Interface proof (VERIFIED)**: the Agent reads only `/status` + `/legal_actions`; the served step record
  contains no scenario name/ID/seed (only own units, active/passive contacts, time). The Agent therefore has
  no channel to read scenario identity. `grep` confirms no scenario ID/seed in decision code (only docstrings).
- **Scenario Rename Test / Hidden Metadata Removal / Situation Perturbation / Skill State Handoff / Episode
  Isolation**: runtime harness for renaming a scenario display name was **NOT_RUN** in this round (budget).
  Honest status: NOT_MEASURED. The interface proof above means renaming cannot change Agent inputs.
- State handoff: C30 keeps lock actions and UAV lifecycle out of the composer override (`lock` untouched;
  UAV RETURN/LANDING not rewritten by safety unless the course would leave the area, which inward returns
  do not). No task-clearing observed in the six-scenario K/L.
