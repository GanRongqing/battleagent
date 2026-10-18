# 13 — FINAL VERSION DECISION
## Evaluation credibility: RESTORED
- Root cause fixed (explicit by-path scenario loading + per-worker temp.py + unique ports).
- All 24 episodes passed Layer-1/2/3 identity; results reproduce historical baselines
  (e.g., ACE W2-6 10/18, W2-4 12/6, W2-2 4/19, W2-1 0/20).
## Answers
1. E7's W2-6 1.077 reproduced? **YES** (14/13, verified identity).
2. W2-4 2.400 still holds? **YES** (12/5).
3. W2-2 regression? **NO** (0.211 -> 0.222, flat/slightly better).
4. C10 + E7 incremental value? **NEGATIVE_TRADEOFF** (best W2-6 but W2-5 -51%, W2-4 worse than ACE+E7).
5. W2-1/W2-3/W2-5: W2-1 0 (unchanged); W2-3 regressed by E7; W2-5 regressed by C10+E7.
6. New overall vs Old Best? Old Best (C10 OFF, pooled 0.725) > ACE+E7 (0.633).
7. Freeze as new candidate? **ACE + LIFECYCLE_HANDOFF_V1=1**, marked **TARGETED_ONLY**.
8. Enough evidence to change the default? **NO.**

## Decision
- `FROZEN_VALIDATION_CANDIDATE = ACE + LIFECYCLE_HANDOFF_V1=1` (**TARGETED_ONLY**: W2-6/W2-4 gain,
  W2-3 regression).
- `BEST_OLD_VERSION = C10 OFF` (pooled 0.725) — retained; C10 stays TARGETED_ONLY.
- `C10+E7` not recommended (W2-5 collapse).
- `GLOBAL_DEFAULT_CHANGED = NO` (all flags off by default).
- Fresh-RNG required before any generalization claim: `FRESH_RNG_NOT_EXECUTED`.
