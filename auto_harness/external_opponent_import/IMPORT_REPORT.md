# IMPORT_REPORT.md — External Opponent Import Pipeline

## Status: WAITING_FOR_EXTERNAL_ARTIFACTS

- Incoming drop zone: `/root/sc2agent/incoming_opponents/{wave1,wave2}` — **both empty**.
- Wave1 artifacts present: **NO** (expect 5)
- Wave2 artifacts present: **NO** (expect 6)
- INCOMING_INVENTORY.csv rows: 0
- STATIC_AUDIT.csv rows: 0
- Black-identity validation: not run (no candidates)
- Smoke: not run (requires 5/5 + 6/6 static pass)
- Freeze: not run

## What was built this round (scaffold only)
- Drop zone + README, quarantine/, extracted/
- `external_opponent_import/README.md`, `BLACK_POLICY_CONTRACT.md`, sandbox `external_wave_registry.json`
- `schemas/` opponent_artifact + opponent_registry JSON schemas
- `tools/` 9 modules: inventory_incoming, extract_archives, classify_artifacts, recover_entrypoints,
  validate_black_identity, build_import_manifest, run_black_smoke, freeze_artifact, build_eval_registry
- `templates/` IMPORT_REPORT + SMOKE_REPORT; `tests/test_pipeline.py` → 3/3 PASS

No evaluation was run. ACE / Frozen W5 / existing Black identities / production registry untouched.

## Next action
Place original Wave1/Wave2 deliveries into:
- `/root/sc2agent/incoming_opponents/wave1/`
- `/root/sc2agent/incoming_opponents/wave2/`
