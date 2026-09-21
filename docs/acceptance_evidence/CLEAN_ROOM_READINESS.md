# Clean Room Readiness

Checklist to reproduce this system on a fresh machine:
- [ ] Copy repo (`hsystem/`) + `githsysys/` git repo.
- [ ] Create env `hsystem_env`; install `hsystem/requirements.txt` PLUS fastapi/uvicorn/pydantic (missing, see DEPENDENCY_AUDIT.md).
- [ ] Start backend: `base_server.py --simserver_num 3` (see BACKEND_STARTUP_REFERENCE.md).
- [ ] Start API: `pomdp_api/main.py` on :8000.
- [ ] Verify `GET /health` == 200 and `GET /scripts` lists scenarios.
- [ ] Set `LLM_ENABLED=false` for deterministic runs (no secret needed).
- [ ] Run `scripts/acceptance/run_single_w5.py` -> expect a terminal result.
- [ ] Run core tests (TEST_INVENTORY.md).
- [ ] Record seeds + scenario JSON for every run.

UNKNOWN: exact OS/conda build reproducibility (CUDA not required for the deterministic path).
NOT_VERIFIED: multi-host deployment; only single-host verified this round.
