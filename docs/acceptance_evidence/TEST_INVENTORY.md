# Test Inventory

| area | file | type | covers | in acceptance run |
|---|---|---|---|---|
| W5 core | agent_hybrid_v5.py --selftest | built-in | TrackManager units | YES |
| W5 scale | agent_hybrid_v5.py --scaletest | built-in | scale generalization | YES |
| W5 units | test_v5_units.py | unit | 37 checks | YES |
| BT interface | test_bt_harness_interface.py | unit | 53 checks | YES |
| BT trees | test_bt_real_trees.py | unit | 60 checks | YES |
| strategy library | test_strategy_library.py | unit | 21 checks | YES |
| policy system | test_policy_system.py | unit | 10 checks | YES |
| policy fp2 | test_policy_fp2.py | unit | 18 checks | regression |
| b0 27class | test_b0_27class.py | unit | 11 checks | regression |
| b0 v2 | test_b0_v2.py | unit | 11 checks | regression |
| anti-leak | test_anti_leak.py | unit | 12 checks | regression |
| phase1.5 | test_phase15.py | unit | 5 checks | regression |
| phase2a | test_phase2a.py | unit | 13 checks | regression |
| phase2b | test_phase2b.py | unit | 11 checks | regression |
