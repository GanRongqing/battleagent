# Decision Authority

| Decision | Stable W5 owner | file:line | BT future owner | MARL future owner |
|---|---|---|---|---|
| WHO fights | ThreatAllocator | agent_hybrid_v5.py:1798 | Harness (Platform) | MARL policy output |
| WHAT (task type) | USVController/UAVManager | :2002 / :2193 | BT phase | MARL task head |
| TARGET | ThreatAllocator.allocate_usvs | :1798 | Harness (Target) | MARL policy output |
| HOW (heading/speed/pursuit) | USVController | :2002 | BT | NOT recommended |
| ACTION LEGALITY | ActionSafety | :2496 | ActionSafety (unchanged) | ActionSafety (unchanged) |
| Intent/doctrine (strategic) | StrategicIntent / LLMCommander (off if LLM_ENABLED=false) | :804 / :1474 | — | — |
