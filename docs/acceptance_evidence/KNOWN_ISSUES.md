# Known Issues

| id | severity | issue | evidence | impact | workaround |
|---|---|---|---|---|---|
| K1 | MED | EPISODES.csv `enemy_breakthrough_count`/`enemy_combat_killed_event` conflict with `[META]`/`/result` | source conflict | metric ambiguity | use `/result` + `[META]`; V2 ledger has provenance |
| K2 | MED | `[ASSIGN]` step-log is a non-canonical proxy (overcounts 9-25%) | phase3 vs phase4/5 | false causal claims | use runtime instrumentation |
| K3 | LOW | `SKILL_MD_SHA256.txt` stale hash | e1f7839a vs 155b0201 | audit confusion | see HASH_CONFLICT_AUDIT.md |
| K4 | LOW | `white_harness_versions.jsonl` W5 hash != file sha | a7842b29 vs e823e7be | audit confusion | use VERSION_MANIFEST.json |
| K5 | MED | requirements.txt missing fastapi/uvicorn/pydantic | DEPENDENCY_AUDIT.md | clean-room install fails | requirements-acceptance.txt |
| K6 | MED | Phase6 oracle arms invalid (tracker-layer injection) | phase6 report | headroom unknown | re-inject at observation layer |
| K7 | LOW | White coords not recorded in historical logs | only 10-episode replay set has them | limited replay | use replay set |
