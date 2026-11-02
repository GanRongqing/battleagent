# 06 — UNIT & PHYSICS TESTS
`test_scenario_agnostic_safety.py` **8/8**: subclass ActionSafety; W2 interior not rewritten; scale octagon interior
(y≈405km) not rewritten; predicted-out near boundary rewritten; UAV fly out rewritten; missing area → no rewrite +
unavailable; invalid polygon → unavailable; lock actions untouched.
Real-engine checks (not just math): S10 C31 = 5/0 (fleet stays at y≈405, engages; previously 0/5); W2-1 C31 = 16/5
with 0 AREA_OUT (buffer). DT=31s aligned with MACRO_STEP=30; UAV 100 m/s and USV 20 m/s covered by 5km buffer.
