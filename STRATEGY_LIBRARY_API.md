# Strategy Library API
## Purpose
Simple metadata registry (CREATE/LIST/GET/PATCH/DELETE) for White/Black strategies. Only
metadata (module entrypoints/hashes) — no code blobs, no execution.
## Data model (StrategyInfo)
strategy_id, name, side(white|black|neutral|system), version, strategy_type(harness|opponent|
skill), status(experimental|active|frozen|completed|deprecated), description, entrypoint,
runtime_mode, parent_id, hash, tags[], metadata{}, created_at, updated_at.
## Endpoints (mounted on the existing sim FastAPI, guarded)
### POST /strategies — create (409 if duplicate, 422 bad side/status)
`curl -X POST http://127.0.0.1:8000/strategies -H 'Content-Type: application/json' -d '{"strategy_id":"white-w9","name":"W9","side":"white","status":"experimental"}'`
### GET /strategies[?side=&status=&strategy_type=] — list + filters
`curl 'http://127.0.0.1:8000/strategies?side=white'`
### GET /strategies/{id} — detail (404 missing)
`curl http://127.0.0.1:8000/strategies/white-w6`
### PATCH /strategies/{id} — update name/status/description/tags/metadata/etc (404 missing)
`curl -X PATCH http://127.0.0.1:8000/strategies/white-w9 -H 'Content-Type: application/json' -d '{"status":"frozen"}'`
### DELETE /strategies/{id} — delete metadata (204; 404 missing)
`curl -X DELETE http://127.0.0.1:8000/strategies/demo-test-strategy`
## Initial strategies (seeded, idempotent)
white-w5(frozen), white-w6(completed, from W6_FINAL_MANIFEST.json), black-b0..b3(frozen).
Run `python seed_strategy_library.py` (idempotent).
## Storage
SQLite (strategy_library/strategy_library.db; override with env STRATEGY_DB_PATH). Auto-init.
## Tests
`python test_strategy_library.py` (21 checks: repo CRUD+conflict+persistence, HTTP CRUD/filters).
## Limitations
Registry metadata only; entrypoints are not executed; strategy_id immutable after create;
created_at immutable (PATCH cannot change).
