# 01 — TEST PLAN (E32)
Frozen strategy: C31 (`white-combat-0031-v1`), no tactic/rule change. 5 primary episodes (L1..L5) + 2 seed
re-checks (L2,L5 @73121). Scenarios are new E32 configs (`scenario_L1..L5`: random_waypoint, fixed_frontage,
enemy_oob=1.0), distinct from E31's S30 (which uses straight_west). Seed 43001 primary; 73121 re-check.
Metrics: Official CER (K/L), Victory, wall time, engine AREA_TRACE (USV/UAV), Safety counters, first contact/lock/kill.
E32 results are reported separately and NOT merged with E31's 13-scenario results.
