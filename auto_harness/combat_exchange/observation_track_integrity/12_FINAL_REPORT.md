# 12 — FINAL REPORT

## Answers
1. Does game-log `active_enemies` contain content the White Agent cannot legally observe? **NO** — it is
   the **legal observation** (`intel["active"]` from `raw["white_observation"]`), identical to the
   `/status` 雷达捕获 the agent receives.
2. Did the C11 Shadow overstate the agent's information? **PARTIALLY (methodology)**: the earlier quick
   shadow mixed W2-4 and W2-6 package logs; but for the true W2-6 FORMs the shadow's expectation
   (enemy in range) was **correct**, and the agent's `obs.active` indeed had it.
3. Is there a confirmed software loss between legal Observation → TrackManager? **YES.**
4. Where? **TrackManager** (`agent_hybrid_v5.py:474-475` + `kill_detect` 537-560) — `killed_names`
   permanently suppresses living, radar-positioned enemies.
5. If no bug, is it normal POMDP partial observability? A bug exists, so not purely POMDP.
6. Is the log coverage sufficient? **YES** — logging-only `obs_dbg` replay provided the agent's actual
   `obs.active`/`tracks` at full step resolution.
7. Fix or stop? **Minimal, env-gated fix implemented + unit-tested; stop the candidate line** (no C12).

## OBSERVATION_ROOT_CAUSE = **TRACK_MANAGER_BUG**
- Primary: `TrackManager.killed_names` over-suppression (false kills from `kill_detect`).
- Secondary: earlier C11 shadow methodology (scenario-mixing) — does not change the conclusion.
- Confidence: **HIGH** (code + full-step trace).

## Scope / impact
- Affects ALL agents sharing `agent_hybrid_v5.TrackManager` (ACE, C10, C11) — a long-standing blindness:
  4042 active-but-untracked unit-steps in one W2-6 episode; usv17 suppressed for 892 steps.
- Explains the "observation gap" that capped W2-6 (and likely W2-1/W2-2) exchange.

## Software change
- One env-gated branch (`OBS_TI_REVIVE`, default 0). Frozen candidates unchanged unless the flag is on.
- **No combat candidate implemented; no full evaluation run; history not overwritten.**
- Running the fixed pipeline for a real re-evaluation is a **new epoch** decision.
