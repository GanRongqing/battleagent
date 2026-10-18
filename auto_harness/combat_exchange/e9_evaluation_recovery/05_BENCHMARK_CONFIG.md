# 05 — BENCHMARK CONFIG
Epoch: `E9` (deterministic, seed 43001). Six scenarios W2-1..W2-6, four configs:
| id | agent | LIFECYCLE_HANDOFF_V1 | OBS_TI_REVIVE | TARGET_LIFECYCLE_V2 |
|---|---|---|---|---|
| A | ACE | 0 | 0 | 0 |
| B | C10 | 0 | 0 | 0 |
| C | ACE | 1 | 0 | 0 |
| D | C10 | 1 | 0 | 0 |
Runner: parallel_runner, 6 workers per batch, one job per worker, unique ports per `run_id`.
Every episode must pass Layer-1/2/3 identity (`scripts/verify_identity.py`). Engine/Black/agents unchanged.
Route per scenario: W2-1 route1, W2-2 route4, W2-3 route3, W2-4 route2, W2-5 route1 (diamond formation),
W2-6 route5.
