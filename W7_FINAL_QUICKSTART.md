# W7 Final Quick Start
W7 final = completed_no_robust_improvement. Best runtime remains W5-equivalent.
- Run W5 (the strongest baseline): SCENARIO_SCRIPT=scenario_composition LLM_ENABLED=false \
  python agent_hybrid_v5.py --uavs   (sim via bash /tmp/opencode/start_services.sh)
- Run W6 (completed adaptive generation): + W6_ANTI_EVASION=1 W6_MODE=dev3 python agent_hybrid_w6.py --uavs
- Smoke: python test_v5_units.py ; python test_w6_units.py
- Strategy library: python seed_strategy_library.py ; GET http://127.0.0.1:8000/strategies/white-w7
Manifest: W7_FINAL_MANIFEST.json
