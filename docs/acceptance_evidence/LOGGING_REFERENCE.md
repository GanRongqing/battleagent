# Logging Reference

| system | path | producer | format | authoritative for |
|---|---|---|---|---|
| POMDP API runtime | hsystem/pomdp_api/api_logs/runtime/ | FastAPI | text | API health/errors |
| POMDP game logs | hsystem/pomdp_api/api_logs/games/game_*.json | API | JSON per step | evaluator truth: per-step White states, active_enemies, actions, reward, result_reason |
| Agent stdout | <runner logs>/S*_*.log | agent_hybrid_v5.py | text | actor legal view: steps, TRACKS, [DETECT]/[ASSIGN]/[RELEASE]/[KILL], [META] |
| runtime_audit | runtime_audit/run_*/ | agent | JSON | per-step A/B/E/F audit |
| formal eval | formal_eval_20260825/, opponent_formal_eval/ | runners | CSV | W5 vs B0/B3 results |
| auto_harness | auto_harness/ | runners/miners | CSV/MD | candidate evolution |
| strategy library | strategy_library/strategy_library.db | policy system | SQLite | cards/artifacts/fingerprints/validations |
| skill evolution | skill_evolution_runs/ | skill_evolution.py | JSON/MD | offline skill versions |

NOT authoritative: step-level `[ASSIGN]` for canonical assignment; `EPISODES.csv` when conflicting with `/result`.
