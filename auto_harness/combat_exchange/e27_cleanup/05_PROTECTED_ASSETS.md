# 05 — PROTECTED ASSETS (verified present)
- Engine compiled extensions in place: `hsystem/simulation/{core,arsenal}/*.so` (5 files, 4.3M) — NOT in build.
- Engine source, judge/score/radar/physics, scenario/area/route data: untouched.
- `.venv` (separate Python 3.8 env, ~1.1G) — kept (not in our run chain, but could be shared).
- `hsystem/.git` (82M, engine repo) and `githsysys/.git` (59M, deliverable) — untouched.
- C30 stack: `agent_hybrid_split_screen.py`, `agent_hybrid_safe_recon.py`, `agent_hybrid_fleet_recon.py`,
  `agent_hybrid_press_search.py`, `agent_hybrid_budget_gate.py`, `agent_hybrid_v5.py`, `adaptive_skills.py`,
  `universal_safety.py`, `run_agent_wrapper.py`.
- Evidence: e24/e25/e26 reports + `raw_logs/games_c27` (6 gz), `raw_logs/games_c30` (6 gz), results JSONL,
  AREA_TRACE, LOCK_TRACE, ablation/six-scenario CSVs.
