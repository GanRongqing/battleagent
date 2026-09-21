# Evaluation Commands

All Python via `/root/miniconda3/envs/hsystem_env/bin/python` (run from repo root).

```bash
# single canonical W5 episode (LLM off)
python scripts/acceptance/run_single_w5.py

# external opponents
python run_external_opponent.py --help

# formal W5 vs Black profiles
python run_opponent_formal.py

# white phase1 (anti-leak)
python run_white_phase1.py

# b0-v2 calibration
python run_b0_v2.py

# two-sided replay set
python run_replay_set.py && python verify_replay_set.py

# common calibration (fp-v2)
python common_policy_calibration.py

# core tests
python test_v5_units.py
python test_bt_harness_interface.py
python test_bt_real_trees.py
python test_strategy_library.py
python test_policy_system.py
python agent_hybrid_v5.py --selftest
python agent_hybrid_v5.py --scaletest
```
