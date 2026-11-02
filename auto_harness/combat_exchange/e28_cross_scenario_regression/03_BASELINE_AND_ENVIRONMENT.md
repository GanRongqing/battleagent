# 03 — BASELINE & ENVIRONMENT
- Engine hash (from /start identity): recorded per result (`EngineHash`/`ScenarioHash`).
- Agent entry: `run_agent_wrapper.py` → `budget` (C10) / `splitscreen` (C30).
- Both C10 and C30 run on the same scenario/seed/engine/API in the same invocation (paired).
- Seed: 43001 (requested == actual; lock RNG is seed-independent per E12, so nominal different seeds may
  reproduce identical trajectories — only real independent seeds count).
- Runner fix (E28 adapter, no behaviour change): worker `_symlink_farm` was missing `sim_script`, so
  scale-scenario wrappers (which compute `_SRC=dirname(cwd)/sim_script/20250819TZB`) failed to import and the
  engine stayed empty (`/start` 200 with engine=None). Added a symlink of repo `sim_script` into the worker
  dirs. Verified by a real S10 episode (C10 = 5/1, valid).
- W2 baseline smoke: E27 post-cleanup C30 W2-2 = 30/8 valid (matches E26 reference).
