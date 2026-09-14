# 06 — Strategy Library & Policy System

## 1. Database
SQLite: `strategy_library/strategy_library.db`. Tables (verified):
`strategies`, `policy_cards`, `policy_artifacts`, `policy_fingerprints`, `policy_validations`.
Row counts (current): policy_cards 7, policy_artifacts 7, policy_fingerprints 7, policy_validations 11.

## 2. Policy cards (7)
See `data/master_policy_table.csv`. Side/family/status/role for each policy; White candidate
`white-auto-0001-v1` is side=white, family=anti_leak_containment, status=candidate.

## 3. Artifacts (7)
See `data/master_artifact_registry.csv`. Each manifest records entrypoint, artifact_hash,
bundle_hash, environment/simulator/opponent-module hashes. Bundles are unique per policy;
B0-v1/B1/B2/B3 share `opponent_profiles.py` (hash 7aa12e1d8b7c) but differ by entrypoint/logic.

## 4. Fingerprints
| policy | versions | episodes | notes |
|---|---|---|---|
| black-b0-v1 | fp-v1, fp-v2 | 93, 10 | fp-v1 legacy formal; fp-v2 S2 common calibration |
| black-b1-v1 | fp-v2 | 10 | S2 common calibration |
| black-b2-v1 | fp-v2 | 10 | S2 common calibration |
| black-b3-v1 | fp-v1, fp-v2 | 93, 10 | fp-v1 legacy formal; fp-v2 S2 common calibration |
| black-auto-0001-v1 | fp-v2 | 10 | includes fp-v3 structural group |

- fp-v1: legacy flat behavior/response signature (93-ep B0/B3 formal).
- fp-v2: behavioral (temporal/spatial/coordination/adaptation) + response (outcomes) separated.
- fp-v3: generic structural features (reserve_fraction, early/late commitment, role_asymmetry,
  dominant_axis_shift_count, phase_switch_count, continuous_replan_count) — used for AUTO1.
- `/policies/{id}/fingerprint/latest` returns fp-v2 when present (fp-v1 preserved).

## 5. Validations (11)
See `data/master_experiment_registry.csv` + section 3 of `04_...`. Key: B1-vs-B2 INCONCLUSIVE;
all AUTO1 pairs DISTINCT; B0-vs-B3 duplicated across fp versions (SOURCE CONFLICT, see 02/04).

## 6. API (FastAPI, mounted in `hsystem/pomdp_api/main.py`)
`GET /policies/{id}`, `/artifact`, `/fingerprints`, `/fingerprint/latest`,
`GET /policies/{id}/compare/{other}`, `POST /policies/{id}/seal`.
`compare` returns separated blocks: artifact / declared_semantic / behavioral / response /
multi_seed / multi_scenario / verdict (fp-v2 path).

## 7. Modules
`strategy_library/`: `policy_models.py`, `policy_repository.py`, `fingerprint.py`,
`policy_compare.py`, `policy_router.py`, `policy_fp2.py`, `policy_fp3.py`, `fp2_analysis.py`, `seed_policies.py`.
(root-level: `seed_calibration_fp2.py`, `auto_evolution_analysis.py`, `auto_register.py`).

## 8. Lifecycle
candidate → dev → validation → active/sealed. Sealing requires candidate/dev/validation status;
`active` is the pool-ready state. black-b0-v1 is `sealed` (historical anchor).
