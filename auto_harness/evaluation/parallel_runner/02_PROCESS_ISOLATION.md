# 02 — PROCESS ISOLATION
Each Worker builds a private runtime dir `parallel_runs/<run_id>/w<i>/`:
- `simserver/` — symlink farm of the shared (read-only) `hsystem/simserver`. Because it is the worker's
  cwd, `base_server.py` writes `temp1.py` and `sim_server.py` writes `temp.py` HERE (not shared).
- `seed.txt` — the worker's private `RW_SEED_FILE` (engine reads it at `/start`).
- `api_logs/` — FastAPI game logs + runtime log (`API_LOG_DIR` override in `pomdp_api/main.py`).
- `base_server.log`, `api.log`, `ep_<seed>_<agent>.log` — per-worker stdout/stderr.

Ports: base_server `6010+10w`, sim_server `6011+10w`, FastAPI `8010+10w`; asserted free before start.

Shared mutable files removed:
- global `/tmp/opencode/seed_w0.txt` -> per-worker `seed.txt`
- shared `simserver/temp.py`, `simserver/temp1.py` -> per-worker cwd
- shared `pomdp_api/api_logs/**` -> per-worker `API_LOG_DIR`
No Worker connects to another Worker's simulator. Read-only code/assets are shared via symlinks.
