# 05 — FAIRNESS GATES (pre-run)
| Gate | requirement | result | evidence |
|---|---|---|---|
| F1 数量对等 | White USV==Black USV, White UAV==Black UAV | **PASS 16/16** | 02_FAIR_FORCE_CONFIGS (30/20/24/45; UAV 0==0) |
| F2 装备对等 | same radar/speed/weapon for same-type platforms | **PASS** | 03 (radar 30==30, speed 20==20, same locker) |
| F3 部署合法 | all units inside area, no overlap, capacity ok | **PASS** | 04 (in-process build, F13 90 platforms ok) |
| F4 环境规则不变 | judge/physics/radar/weapon/terminal unchanged | **PASS** | only scenario-level config (formation + radar env); engine untouched |
| F5 黑方战术保持 | 16 original routes unchanged | **PASS** | same route files/SHA256; only White formation_mode changed |
| F6 C31 冻结 | C31 == E31 release | **PASS** | agent_hybrid_c31.py + scenario_agnostic_safety.py unchanged (5 km buffer) |
| F7 无场景信息泄漏 | no route-ID/name/seed branching | **PASS** | C31 uses only obs + public polygon; configs are engine-side |
Note: any scenario that could not meet parity would be marked PARITY_UNRESOLVED; none required it (Black unchanged, counts/capability matched by construction).
