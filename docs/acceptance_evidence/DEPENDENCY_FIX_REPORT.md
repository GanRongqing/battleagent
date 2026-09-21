# Dependency Fix Report

## Problem
`hsystem/requirements.txt` did not list the Web API runtime dependencies used by
`hsystem/pomdp_api/main.py` (imports at main.py:44-47, 1885).

## Change
Added a "Web API 运行时" section to `hsystem/requirements.txt`:
```
fastapi>=0.100.0
uvicorn>=0.23.0
pydantic>=2.0.0
```
Existing scientific/simulator deps (numpy/pandas/scipy/shapely/pyproj/networkx/matplotlib/
cython/numba/grpcio/protobuf/nats-py/redis/requests/dill/json5/allpairspy) were PRESERVED.

## Verified installed versions (this env)
fastapi 0.124.4 | uvicorn 0.33.0 | pydantic 2.10.6 | grpcio 1.70.0 | protobuf 3.20.0 |
requests 2.32.4 | numpy 1.24.4 | pandas 2.0.3 | scipy 1.10.1.

## Import smoke
Command: `/root/miniconda3/envs/hsystem_env/bin/python scripts/acceptance/import_smoke.py`
```
OK   fastapi
OK   uvicorn
OK   pydantic
OK   grpc
OK   requests
OK   numpy
OK   pandas
----------------------------------------
IMPORT_SMOKE = PASS (7 modules)
```

## Notes
- `python-multipart` is NOT required (main.py does not use Form/File/UploadFile).
- `docs/acceptance_evidence/requirements-acceptance.txt` retained as the acceptance snapshot.
- Full `pip freeze` is NOT copied into requirements (kept minimal).
