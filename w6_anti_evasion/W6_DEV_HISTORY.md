# W6 DEV History

## DEV revision 1 (2026-08)

**Scope**: component sanity — White 5+5 vs Black 10, B0/B3, paired seeds 2001-2003, W5 vs W6.
12 episodes. DEV seeds only (2001-2003); formal 1001-1030 untouched.

### Result (component_sanity.csv)

| opponent | seed | W5 | W6 |
|---|---|---|---|
| B0 | 2001 | V clean, usv_dead 1 | V clean, usv_dead 0 |
| B0 | 2002 | V clean, usv_dead 3 | V quirk(breakthrough), usv_dead 5 |
| B0 | 2003 | V clean, usv_dead 3 | V clean, usv_dead 0 |
| B3 | 2001 | V clean, usv_dead 0 | **D**, usv_dead 5 |
| B3 | 2002 | V clean, usv_dead 1 | V clean, usv_dead 2 |
| B3 | 2003 | V quirk, usv_dead 0 | **D**, usv_dead 2 |

### Mechanism fire-check

| mechanism | fired? |
|---|---|
| predictive_intercept | YES (3891 predictions/intercepts in W6 s2001) |
| pursuit_cost allocator | YES (allocation differs; intercept aimed at corridor) |
| handoff | **NO — 0 handoffs across all sanity episodes** |
| uav_track_maintenance | **NO — 0 maintenance assignments** |
| adaptive_screen | YES (496 screen assignments in s2001) |
| breakthrough_horizon | YES (risk computed; alerts present) |

### Gate check (task §26)

- W6 B0 clean = 2/3 vs W5 B0 clean = 3/3 → **B0 regression >20pt (rule: stop + audit)**.
- W6 B3 = 2 defeats vs W5 B3 = 0 defeats → worse, not better, on the primary target opponent.
- handoff + track-maintenance did NOT trigger (features present but inert).

### Actions for DEV revision 2 (mechanism audit, NOT blind tuning)

1. **handoff**: W6 allocation already picks the best interceptor, so alternates rarely beat it by
   the 25% hysteresis. Investigate whether handoff should compare against the CURRENT committed
   interceptor (not the best) and whether ETA margin normalization is too strict. Also confirm
   the base allocator's reserve/coverage keeps alternates available.
2. **predictive intercept loss spike**: W6 USV losses are up (B0 s2002 5 dead, B3 5 dead).
   Audit whether the corridor intercept point pulls interceptors inside the target's weapon
   band (intercept point near target) → increase standoff separation in InterceptPlanner.
3. **B0 quirk (breakthrough) at s2002**: W6 broke the B0 baseline on one seed — check whether
   the screen reserve left too few committed interceptors or the predictive aim caused a late
   cover switch.

## Reclassification (W6-dev3 start)

Seeds 4001-4010: previously used as the three-stage co-evolution "FINAL" holdout for
W6-dev2 (90 episodes, `coevolution_final/final_episode_results.csv`). Because those runs
were used to observe W6-dev2 failures and to design W6-dev3, seeds **4001-4010 are now
DIAGNOSTIC / DEVELOPMENT EVIDENCE** and must NOT be treated as an unseen FINAL holdout
going forward. The future W6-dev3 FINAL must use fresh seeds (5001-5010).
