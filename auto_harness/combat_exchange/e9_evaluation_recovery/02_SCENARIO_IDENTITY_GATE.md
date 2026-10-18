# 02 — SCENARIO IDENTITY GATE (fail-closed)
`scripts/verify_identity.py <run_id> <sid> <policy>`:
- Layer 1 (requested): run job config / plan.
- Layer 2 (loaded): worker `simserver/temp.py` (real file) strategy_filename.
- Layer 3 (effective): `runtime_identity.json` route_digest == expected digest computed from the frozen
  `sim_script/scenario/route/<route>.json` (canonical SHA-256); formation_mode recorded.
- Log attribution: game-log script_name == plan.
- Result validity.
`SCENARIO_IDENTITY_VALID = all`. Any mismatch → INVALID, excluded from statistics.
Expected digests: route1 `21ffcf3a…`, route2 `165edc8b…`, route3 `ce9507ff…`, route4 `b53386b7…`,
route5 `4b80fe82…`, route6 `47b96fad…`.
