# Strategy Library Acceptance

- Package: `strategy_library/` (`policy_models.py`, `policy_repository.py`, `fingerprint.py`,
  `policy_compare.py`, `policy_router.py`, `policy_fp2.py`, `seed_policies.py`).
- Storage: `strategy_library/strategy_library.db` (SQLite), tables: `policy_cards`,
  `policy_artifacts`, `policy_fingerprints`, `policy_validations`.
- Mounted (guarded) into `hsystem/pomdp_api/main.py`.
- Registered policy_ids (see POLICY_REGISTRY_SNAPSHOT.json): black-b0-v1, black-b1-v1,
  black-b2-v1, black-b3-v1, black-b0-v2, black-auto-0001-v1, white-auto-0001-v1,
  white-auto-0002-v1, white-auto-0003-v1.
- Tests: `test_strategy_library.py` 21/21 PASS, `test_policy_system.py` 10/10 PASS,
  `test_policy_fp2.py` 18/18 PASS.
- Fingerprint: fp-v1 retained; fp-v2 common calibration B1 vs B2 INCONCLUSIVE (dist 0.371).
