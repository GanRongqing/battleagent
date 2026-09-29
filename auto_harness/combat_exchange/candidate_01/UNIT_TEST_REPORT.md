# Unit Test Report — white-combat-0001-v1

`test_combat_c1.py` — 6/6 PASS:
- test_kill_opportunity: no track -> no opp; track in/out of LOCK_RANGE -> opp/no-opp.
- test_nearest_friendly: correct min-distance.
- test_retreat_fires_when_exposed_no_opp_far_support: exposed+no-opp+far-support -> retreat
  toward friendly (not default patrol).
- test_no_retreat_with_kill_opportunity: exposed but lockable target -> still locks (no retreat).
- test_no_retreat_with_nearby_support: exposed but support < 50km -> stays.
- test_w5_hash_unchanged: W5 sha unchanged.
