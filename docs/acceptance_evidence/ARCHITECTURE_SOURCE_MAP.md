# Architecture Source Map (from current source)

All line numbers are from the current working tree (`agent_hybrid_v5.py` etc.).

| component | file | class/function | line | input | output | caller | callee | runtime role |
|---|---|---|---|---|---|---|---|---|
| HTTP client | agent_hybrid_v5.py | `ApiClient` | 147 | HTTP | dict | AgentMain | :8000 API | status/apply/result |
| observation | agent_hybrid_v5.py | `Obs` | 203 | /status json | obs object | step_once | TrackManager | legal obs parse |
| legal actions | agent_hybrid_v5.py | `LegalSet` | 237 | /legal_actions | wrapper | step_once | USVController | legality |
| tracks | agent_hybrid_v5.py | `TrackManager` | 458 | obs | events | step_once | — | belief state |
| coverage | agent_hybrid_v5.py | `CoverageMap` | 600 | UAV pos | coverage | step_once | UAVManager | sensing map |
| allocation | agent_hybrid_v5.py | `ThreatAllocator.allocate_usvs` | 1718 / 1798 | tracks,usvs,usv_map | {target:[usv]} | step_once | — | WHO/TARGET |
| USV exec | agent_hybrid_v5.py | `USVController.step` | 1969 / 2002 | alloc_result | actions | step_once | ActionSafety | HOW |
| UAV exec | agent_hybrid_v5.py | `UAVManager.step` | 2162 / 2193 | tracks | actions | step_once | — | sensing tasks |
| safety | agent_hybrid_v5.py | `ActionSafety` | 2496 | actions | filtered | step_once | /apply | legality gate |
| main loop | agent_hybrid_v5.py | `AgentMain.run` / `step_once` | 2963 / 2793 | — | — | __main__ | all above | orchestration |

## End-to-end chain
`HTTP API` → `ApiClient` → `Obs`/`LegalSet` → `TrackManager` → `ThreatAllocator` → `USVController`/`UAVManager` → `ActionSafety` → `POST /apply` → `Simulator`.
