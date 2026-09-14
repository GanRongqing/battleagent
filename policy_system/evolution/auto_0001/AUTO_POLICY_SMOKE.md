# AUTO_POLICY_SMOKE — black-auto-0001-v1 (AUTO_FEINT_SWITCH)

White = frozen W5, S2, seeds 7001-7003, N=3 (mechanism smoke, not strength).

| seed | result | clean | wall_s | phase_switches | replan_count | response_trigger | timeout_switch | reserve_commit | final phase |
|---|---|---|---|---|---|---|---|---|---|
| 7001 | Defeat | 0 | 343.6 | 2 | 13 | 0 | 1 | 1 | DEGRADED |
| 7002 | Victory | 1 | 245.9 | 2 | 14 | 0 | 1 | 1 | DEGRADED |
| 7003 | Victory | 1 | 187.1 | 1 | 13 | 0 | 1 | 1 | DEGRADED |

Checks:
- phase transitions firing: YES (1-2 discrete switches per episode)
- feint group exists: YES (roles 4/13/3 at n=20)
- main group delayed: YES (main/reserve hold east until switch; main_commit_time ~7000s)
- switch happens: YES (timeout fallback; response trigger not observed in these 3 seeds)
- main push happens: YES
- reserve commit happens: YES
- no OOB / no crash: YES (no abnormal episodes)
- fingerprint trace readable: YES (black_behavior_trace + auto_events sidecars)
- low continuous replanning: YES (replan ~13 vs B3 ~620)

Note: in v1 the legal RESPONSE_TRIGGER did not fire within FEINT_TIMEOUT on these seeds;
all switches used the bounded TIMEOUT fallback. Behavior remains phased/role-asymmetric.
No logic change made (immutable v1); if response triggering is required empirically a
black-auto-0001-v2 would be created.
