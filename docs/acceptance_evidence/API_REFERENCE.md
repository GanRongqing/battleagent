# API Reference (stable W5 API: hsystem/pomdp_api/main.py)

| method | path | function line | used by W5 | side effect |
|---|---|---|---|---|
| GET | `/` | 1340 | no | info |
| GET | `/health` | 1385 | no | none |
| GET | `/scripts` | 1417 | no | none |
| POST | `/start` | 1429 | YES | starts engine/scenario |
| GET | `/stop` | 1487 | YES | stops engine |
| POST | `/reset` | 1532 | no | reset |
| GET | `/status` | 1578 | YES | none (read) |
| GET | `/obs` | 1681 | **NO** (agent uses /status + /legal_actions) | none |
| GET | `/legal_actions` | 1700 | YES | none |
| POST | `/apply` | 1723 | YES | submits actions |
| GET | `/result` | 1834 | YES | none (authoritative terminal) |
| GET | `/game_log` | 1862 | no | none |

Note: `target_speed` schema documented as "0-100 m/s" (main.py:962). `/obs` exists but the frozen W5 agent does NOT call it (uses `/status` + `/legal_actions`).
