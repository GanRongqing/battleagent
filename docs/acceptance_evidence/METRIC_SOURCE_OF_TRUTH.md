# Metric Source of Truth

| metric | definition | primary source | fallback | actor-visible | evaluator-only | caveat |
|---|---|---|---|---|---|---|
| Victory/Defeat | engine terminal result | `GET /result` (authoritative; W5 run() uses it) | `[META] result=` in agent log | yes | no | `/status` counters may lag vs `/result` |
| Clean win | victory AND 0 breakthrough | runner (clean_win from /result + breakthrough) | — | yes | no | — |
| Black killed | kills | `[META] enemy_kills` | `[KILL] black_usvN` lines | yes (kills it made) | no | EPISODES `enemy_combat_killed_event` may disagree (SOURCE CONFLICT) |
| Black breakthrough | enemies crossing boundary | `GET /result` reward `black_breakthrough` / `result_reason` | `[META] black_breakthrough` | yes | no | EPISODES `enemy_breakthrough_count` may disagree |
| White USV loss | friendly losses | `[META] friendly_usv_losses` | game log usv_states dead | yes | no | — |
| White UAV loss | friendly UAV losses | `[META] friendly_uav_losses` | — | yes | no | — |
| Resolution time | sim seconds to end | `[META] victory_time` | game log last sim_time | yes | no | — |
| Detection | enemy seen | game log `active_enemies` / `[DETECT]` | — | yes | no | oracle arms: NOT valid (injected tracks bypass radar) |
| Canonical allocation | real allocator owner transition (None->USV) | runtime instrumentation (`agent_hybrid_w5_translog.py`) | step-log `[ASSIGN]` (proxy) | yes | no | `[ASSIGN]` proxy overcounts 9-25% |
| Lock active | first lock | game log `锁定` actions | — | yes | no | — |
| ISR | intercepted/(intercepted+breakthrough) | interception ledger | — | evaluator | yes | UNRESOLVED reported separately |
| Interception Coverage | intercepted/total_black | interception ledger | — | evaluator | yes | — |
| Breakthrough Rate | breakthrough/total_black | interception ledger | — | evaluator | yes | — |
| Unresolved Rate | unresolved/total_black | interception ledger | — | evaluator | yes | — |

## Proxies that are NOT canonical causal evidence
- step-level `[ASSIGN]` logs (overcount; caused the refuted Phase3 AE-F5).
- `EPISODES.csv` kills/breakthrough when they conflict with `[META]`/`/result`.
- oracle-injected track availability (diagnostic only).
