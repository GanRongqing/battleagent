# BT Integration Reference

- Interface: `test_bt_harness_interface.py` (53 checks PASS) defines the harness<->platform contract.
- Trees: `test_bt_real_trees.py` (60 checks PASS).
- Role in stable W5: NOT used (W5 = ThreatAllocator + USVController/UAVManager).
- BT is a FUTURE execution/intent option; platform layer is independent and testable.
- Authority boundary: BT may own WHAT/HOW, but MUST delegate ACTION LEGALITY to ActionSafety (unchanged).
