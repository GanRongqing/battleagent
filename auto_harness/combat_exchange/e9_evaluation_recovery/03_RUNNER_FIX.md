# 03 — RUNNER / LAUNCH FIXES
1. `worker_runtime._symlink_farm`: skip `temp.py`/`temp1.py`.
2. `worker_runtime.Worker`: unique ports from `run_id`; `start()` sweeps own ports.
3. `worker_runtime`: set `RUNTIME_IDENTITY_FILE` and `SCENARIO_MODULE_DEBUG` per worker.
4. `sim_server.py`: deterministic by-path scenario loading (`_e9_load_scenario_module`), replacing
   `import temp; importlib.reload(temp)`.
5. `adaptation.build_simulation`: read-only runtime identity write.
No engine combat/sensor/lock/weapon change; no agent tactic change; no Black change.
