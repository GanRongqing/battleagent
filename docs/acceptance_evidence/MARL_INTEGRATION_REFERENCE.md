# MARL Integration Reference

- Recommended integration point: decision output — platform(WHO)/task(WHAT)/target(TARGET).
- Do NOT let MARL own raw low-level control (heading/speed) — keep USVController or a validated BT.
- Observation: reuse the actor-visible obs (`/status` + `/legal_actions`); do NOT train on evaluator-only fields.
- Legality: always route through `ActionSafety` (agent_hybrid_v5.py:2496).
- Reward source: `/result` terminal + canonical metrics (see METRIC_SOURCE_OF_TRUTH.md), not `[ASSIGN]` proxies.
- Reproducibility: fixed seeds + recorded scenario JSON (see SCENARIO_REPRODUCIBILITY.md).
