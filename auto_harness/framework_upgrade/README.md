# Framework Upgrade — Mechanism Memory + Predictor Library

Two framework capabilities added this round (no tactics change, no combat claims):

- **Part A — Mechanism-Level Version Memory** (sidecar): `auto_harness/version_memory/`
  schemas + cards (W5/ACE/C2) + tools + tests + `VERSION_LINEAGE.md`.
- **Part B — Pluggable Predictor Library** (shadow-only): `hsystem/prediction/`
  unified predictor interface + 3 predictors + online scoring + selection + uncertainty + shadow logging.

## Guarantees
- Frozen W5 / ACE / C2 runtime behaviour: **unchanged** (verified by sha in tests).
- Predictor library: **shadow-only** by default (`PREDICTOR_LIBRARY_ACTIVE=false`).
- Version memory: **sidecar only** (not imported by any agent).
