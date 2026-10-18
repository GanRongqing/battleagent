# 03 — RUNNER FIX AND TESTS
Fixes applied (runner only, no engine/agent change):
1. `_symlink_farm` skips `temp.py`/`temp1.py` (per-worker real scenario file).
2. `Worker.__init__` derives unique ports from `run_id`; `start()` sweeps stale listeners first.
Tests:
- Gate (`identity_gate.py`) reads the worker's real `temp.py` and the game-log script_name.
- Isolation: pair signatures MUST differ; observed pairs identical -> runtime isolation still FAILING
  (Defect 3).
- Flag-OFF equivalence, engine/agent hashes unchanged, no behaviour change in the agent.
Status: Defects 1–2 fixed in code; **Defect 3 unresolved -> formal comparison blocked.**
