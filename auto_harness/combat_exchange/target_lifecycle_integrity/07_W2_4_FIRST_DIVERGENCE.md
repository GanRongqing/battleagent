# 07 — W2-4 FIRST DIVERGENCE (ACE OFF vs ON, seed 43001)
Compared the two E4/E2 game logs step by step (same scenario/seed/engine):
- Steps 0–259: **identical actions and active_enemies**.
- **FIRST_ACTION_DIVERGENCE = step 260, sim 02:10:30** — small course change (e.g. white_usv1
  course 162.1 -> 163.9; usv10 26.1 -> 23.1). Consistent with a changed track/target set (revived live
  contacts) altering the intercept course.
- FIRST_ACTIVE_ENEMIES_DIVERGENCE = step 261 (02:11:00) — one step later (consequence of the action).
- FIRST_STATE_DIVERGENCE (agent internal track set / first revive event): **NOT_MEASURED** — the E4 ON
  runs did not log revive events. The first *observable* divergence is the action at 02:10:30.
- FIRST_OUTCOME_DIVERGENCE: OFF 12/6 (1407 steps, Defeat) vs ON 9/20 (834 steps, Defeat) — the early
  cascade after 02:10:30 leads to heavy losses.
**Not** a false-revival signature: revived targets are alive (02); the divergence is downstream behavior.
