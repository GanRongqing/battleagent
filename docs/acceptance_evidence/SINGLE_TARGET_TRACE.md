# Single Target Trace (real, from acceptance episode S2 x B0_RANDOM seed 1001)

Source agent log: docs/acceptance_evidence/run/logs/*.log

| time(s) | stage | event |
|---|---|---|
| 1740 | DETECT | `[DETECT] black_usv8` (first radar contact) |
| 7372 | first_lock | `[META] first_lock=7372` (episode-level first lock) |
| 8113 | ASSIGN | `[ASSIGN] white_usv2->black_usv8(机会锁定)` |
| 9110 | ASSIGN | multi-USV join: white_usv3/usv4/usv7 -> black_usv8 |
| 9491 | KILL | `[KILL] black_usv8` |
| 9491 | RELEASE | `[RELEASE] white_usv7->black_usv8(目标失效)` |

Actor-visible: yes (agent stdout). Evaluator corroboration: game log + `/result`.
Caveat: `[ASSIGN]` is a step-log proxy; canonical allocator instrumentation is the
causal source (see METRIC_SOURCE_OF_TRUTH.md).
