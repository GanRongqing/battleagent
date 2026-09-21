# Dependency Audit

| package | used_by | in_requirements | installed | min_runtime | status |
|---|---|---|---|---|---|
| fastapi | hsystem/pomdp_api/main.py | True | yes | YES | OK |
| uvicorn | hsystem/pomdp_api/main.py | True | yes | YES | OK |
| pydantic | hsystem/pomdp_api/main.py | True | yes | YES | OK |
| grpc | sim_client | True | yes | YES | OK |
| requests | agent_hybrid_v5.py | True | yes | YES | OK |
| numpy | simulation | True | yes | YES | OK |
| pandas | simulation | True | yes | no | OK |
| scipy | simulation | True | yes | no | OK |
| matplotlib | simulation | True | yes | no | OK |
| shapely | simulation | True | yes | no | OK |
| pyproj | simulation | True | yes | no | OK |
| networkx | simulation | True | yes | no | OK |
| dill | agent_hybrid_v5.py | True | yes | no | OK |

## Verdict

CURRENT_REQUIREMENTS_COMPLETE = NO

Missing from hsystem/requirements.txt but required by the stable runtime: **fastapi**, **uvicorn**, **pydantic** (POMDP API server).
