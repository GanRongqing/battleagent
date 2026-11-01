# 01 — EXECUTABLE SKILL REGISTRY (runtime, not markdown-only)
| axis | skill | code | applies when | exit/disable | notes |
|---|---|---|---|---|---|
| USV maneuver | ACTIVE_SEARCH | C19 `_move` east-redirect | no live threat & boundary safe | threat appears / near boundary | press east to gain contact |
| USV maneuver | DEFENSIVE_SCREEN | C10 `USVController` screen | fallback / composer not active-search | — | C10 base |
| USV maneuver | CONTACT_MAINTENANCE | C10 target/standoff path | live ship track exists | target lost | keeps lock chains, standoff band |
| USV maneuver | POSITION_RECOVERY | `universal_safety` + composer | boundary margin < 40 km | margin restored | steers to area centre |
| UAV recon | FLEET_TETHERED_RECON | `FleetTetheredUAVManager` | no live threat | threat tracked | tether 30 km ahead of front, y-spread |
| UAV recon | BROAD_SEARCH | base `UAVManager` | live threat exists | — | coverage-grid search |
| UAV recon | SAFE_RETURN | base UAV FSM | battery/RTB | — | never preempted |
| Engagement | COOPERATIVE_ALLOCATION | C10 `BudgetGateController`/allocator | always | — | unchanged lock/alloc path |
All skills consume only `obs`/`tracks`/`legal`; no scenario ID/seed.
