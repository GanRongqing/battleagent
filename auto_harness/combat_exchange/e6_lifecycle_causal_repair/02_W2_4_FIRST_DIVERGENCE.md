# 02 — W2-4 FIRST DIVERGENCE (ACE, seed 43001, traced OFF vs ON)
Logging-only trace (agent_hybrid_lifecycle_dbg.py) of both runs; identical scenario/seed/engine.

| transition | step | sim_time | evidence |
|---|---|---|---|
| FIRST_INTERNAL_STATE_DIVERGENCE | 260 | 7800 | `kill_detect` marks **usv13** dead (still live) |
| FIRST_TRACK_DIVERGENCE | 261 | 7830 | OFF tracks lack usv13; ON has usv13 (revived) |
| FIRST_KILLED_NAMES_DIVERGENCE | 261 | 7830 | OFF {usv13}; ON {} |
| FIRST_REVIVE | 261 | 7830 | usv13 revoked on fresh positioned obs |
| FIRST_TASK/ASSIGNMENT_DIVERGENCE | 272 | 8160 | assignment dict changes (OFF 15 units vs ON 10) |
| FIRST_ACTION_DIVERGENCE | 272 | 8160 | action_hash 584b19fa6542 -> 9f006f411790 |
| FIRST_OUTCOME_DIVERGENCE | — | — | OFF 12/6 (2.000) vs ON 9/20 (0.450) |

OFF trace also produces the same first false kill at step 260 (usv13) but **suppresses** it (no revive),
so track/assignment/action stay on the winning path.
ON trace totals: 139 revive events; offline verifier reports 209 `ACTIVE_AFTER_KILL` unit-steps.
