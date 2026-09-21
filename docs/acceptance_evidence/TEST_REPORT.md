# Test Report

| test | command | duration_s | result | excerpt |
|---|---|---|---|---|
| v5_selftest | /root/miniconda3/envs/hsystem_env/bin/python agent_hybrid_v5.py --selftest | 0 | PASS | === TrackManager 全部通过 === |
| v5_scaletest | /root/miniconda3/envs/hsystem_env/bin/python agent_hybrid_v5.py --scaletest | 0 | PASS | === Scale Generalization 全部通过 === |
| v5_units | /root/miniconda3/envs/hsystem_env/bin/python test_v5_units.py | 0 | PASS | PASS: 37  FAIL: 0 |
| bt_interface | /root/miniconda3/envs/hsystem_env/bin/python test_bt_harness_interface.py | 0 | PASS | PASS: 53  FAIL: 0 |
| bt_real_trees | /root/miniconda3/envs/hsystem_env/bin/python test_bt_real_trees.py | 0 | PASS | PASS: 60  FAIL: 0 |
| strategy_library | /root/miniconda3/envs/hsystem_env/bin/python test_strategy_library.py | 2 | PASS | PASS: 21  FAIL: 0 |
| policy_system | /root/miniconda3/envs/hsystem_env/bin/python test_policy_system.py | 1 | PASS | PASS: 10  FAIL: 0 |
