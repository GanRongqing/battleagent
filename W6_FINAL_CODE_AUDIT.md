# W6 Final Code Audit (read-only)
- W6 runtime entry = agent_hybrid_w6.py (W6Agent subclass of agent_hybrid_v5.AgentMain)
- Available W6 modes (env W6_MODE): dev2 (default, execution override ON), dev3 (decoupled,
  execution override OFF), dev4 / dev4_1 / dev4_2 (commitment + experimental triggers),
  prediction_only, w5. Feature gates in anti_evasion/config.py.
- RECOMMENDED W6 DELIVERABLE MODE = dev3 (stable, fair-play, legacy execution; excludes the
  falsified dev4.1/dev4.2 triggers). W6_ANTI_EVASION=1 + W6_MODE=dev3.
- parent baseline = agent_hybrid_v5.py (W5, unchanged).
- USV execution controller = legacy W5 USVController (agent_hybrid_v5); UAV = legacy UAVManager.
- allocator modules = anti_evasion/{motion_predictor,intercept_planner,pursuit_cost,handoff,
  track_criticality,adaptive_screen,breakthrough_risk,w6_harness}.commitment/releasable_pool/
  elastic_reserve (dev4). metrics.py instrumentation.
- fair-play boundary: legal observation only; static leakage tests in test_w6_units.py T9,
  test_opponent_profiles.py; no opponent-profile/seed branches.
- version record: white_harness_versions.jsonl (W6-dev1..dev4.2 + W6-final alias).
- tests: test_w6_units.py, test_w6_dev3_units.py, test_w6_dev4_units.py,
  test_w6_dev4_1_units.py, test_w6_dev4_2_units.py (all green).
