# 01 — SCENARIO IDENTITY ROOT CAUSE (final)
Two defects were found and one fixed; a third remains unverified.

## Defect 1 (fixed): generated scenario file was a shared symlink
`worker_runtime._symlink_farm` symlinked `hsystem/simserver/temp.py`; `sim_server` writes the loaded
scenario into `DIR/temp.py` (lines ~235/257), so the write followed the symlink into the **shared** tree.
Concurrent workers overwrote each other's scenario. Evidence: the worker's `temp.py` was a symlink and the
shared file held `路线2` for W2-6/W2-4 workers.
Fix: never symlink `temp.py`/`temp1.py` -> per-worker real file.

## Defect 2 (fixed): fixed ports -> stale engine/scenario reuse across sequential runs
Each Worker used fixed ports (`6010+10*w`, `8010+10*w`). A leftover `sim_server` (observed `--port 6011`)
survived cleanup, so the next invocation's base_server on the same ports could reuse the previous
episode's engine/scenario. Evidence: the four E8.1 runs collapsed into **two identical pairs**
(W2-2==W2-1 enemy signature `d92460ad1937`, 12/8; W2-6C10==W2-4C10 `be32f92411de`, 12/5), and W2-6's
12/5 equals E7's W2-4 12/5 — i.e. the run reused the W2-4 scenario.
Fix: per-run unique ports derived from `run_id` + pre-start `_sweep()` of any stale listener.

## Defect 3 (UNRESOLVED): runtime identity not independently verifiable
Even with distinct per-worker real `temp.py` (route1 vs route4), the **effective Black behaviour was
identical** across those runs. `temp.py` (what the API asked to load) is therefore NOT proof of what the
simulator executed (`import temp; importlib.reload(temp)` may use a cached/other module). A runtime
identity signal from the engine (e.g., loaded route hash / blue-waypoint digest) is required.
