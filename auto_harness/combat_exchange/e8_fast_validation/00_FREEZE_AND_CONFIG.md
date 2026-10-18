# 00 — FREEZE AND CONFIG (E8)
- Parent commit `77f68c7`. Candidate code changes this round: **NONE**.
- ACE `7527253c…`, C10 `886577b5…`, C11 `07d1ffa9…`, `agent_hybrid_v5.py` (E7) `71e7f406…`,
  engine `locker.py` `130f9c65…` — unchanged.
- Black/scenarios/sensor/locker unchanged. Defaults unchanged (all flags OFF by default).

## E7_WINNING_CONFIG (verified from the E7 run command + source)
| flag | value | notes |
|---|---|---|
| `LIFECYCLE_HANDOFF_V1` | **1** | the single mechanism; independent of `_lc_enabled` |
| `OBS_TI_REVIVE` | **0** | handoff supersedes it (legacy leaves `_KILLED` stale) |
| `TARGET_LIFECYCLE_V2` | **0** (unset) | bookkeeping only; not required for the win |

So the winning config is exactly `LIFECYCLE_HANDOFF_V1=1, OBS_TI_REVIVE=0, TARGET_LIFECYCLE_V2=0`,
passed to every worker via the inherited process env.
