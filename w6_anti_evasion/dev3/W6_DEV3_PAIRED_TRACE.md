# W6-dev3 Paired Trace

Paired seed where dev2 lost and dev3 won: **S1, B3, seed 4002** (deterministic runs,
same frozen opponent/config; only the White version differs).

| metric | W6-dev2 (B) | W6-dev3 (C) |
|---|---|---|
| result | Defeat | Victory (clean) |
| friendly USV dead | 5/5 | 2/5 |
| breakthrough | 0 | 0 |
| resolution time | 24,965 s | 14,660 s |
| USV alive trajectory | 5/5→4/5(38 steps)→3/5→…→0/5 | 5/5→4/5(3)→3/5(17); never < 3 alive |
| W6 execution-override actions | 85 | **0** |

## What differs

dev2 (B) writes a predictive `_w6_intercept` waypoint onto enemy tracks (85 override
actions in this game); that global `predicted_position` override perturbs the legacy
controller's approach/standoff/lock geometry, producing a long attrition spiral
(24,965 s) that ends with all 5 USV dead.

dev3 (C) never writes a waypoint (`execution_override_actions = 0`). Its allocator
reassigned owners / reinforced the imminent threat using only prediction ETA / risk
scalars, and the LEGACY USVController executed approach → standoff → lock → engage
unchanged. Result: faster resolution (14,660 s), USVs kept ≥3 alive, clean win.

## Conclusion

This trace shows the dev3 improvement on this seed comes from returning the execution
semantics to the legacy W5 controller (no waypoint / geometry override), while the
allocator still uses anti-evasion information at the WHO/WHAT/TARGET layer. No physics
buff was involved (sim/opponent identical).
