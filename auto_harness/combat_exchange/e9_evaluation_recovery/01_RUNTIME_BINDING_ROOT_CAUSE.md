# 01 — RUNTIME BINDING ROOT CAUSE (three defects)

## Defect A — shared generated scenario file (fixed)
`worker_runtime._symlink_farm` symlinked `hsystem/simserver/temp.py`; sim_server writes the loaded
scenario into `DIR/temp.py`, so the write followed the symlink into the shared tree and workers
overwrote each other. Fix: never symlink `temp.py`/`temp1.py`.

## Defect B — fixed ports → stale sim_server reuse (fixed)
Workers used fixed ports (`6010+10*w`). A leftover `sim_server` survived cleanup, so the next invocation
on the same ports could reuse the previous engine/scenario. Evidence: a `sim_server --port 6011` was
alive; E8.1's four runs collapsed into two identical pairs. Fix: ports derived from `run_id`, plus a
pre-start sweep of this run's ports.

## Defect C — scenario loaded via `import temp` (THE decisive bug; fixed)
`hsystem/simserver/sim_server.py` loaded the scenario with:
```python
with open(os.path.join(DIR,"temp.py"),"w") as f: f.write(text)
import temp
importlib.reload(temp)
engine = temp.sim(**kwargs)
```
`import temp` resolves through `sys.modules` / `sys.path` / possibly a stale `.pyc`. **Layer-3 runtime
identity proved the executed module was NOT the worker's temp.py**: for a W2-1 request the worker
`temp.py` contained `路线1`, the API `/start` was W2-1, yet the worker's own `sim_server` wrote
`runtime_identity.json` with `strategy_filename="路线2..."` (W2-4 digest `165edc8b732d`, expected
`21ffcf3a30fe`). So the requested/loaded file and the executed scenario diverged inside the module
import, not in the runner label.

### Fix
Load the worker's scenario file explicitly by absolute path under a unique module name:
```python
def _e9_load_scenario_module(path):
    spec = importlib.util.spec_from_file_location("scenario_mod_"+uuid4().hex, path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod
...
mod = _e9_load_scenario_module(os.path.join(DIR, "temp.py"))
engine = mod.sim(**kwargs)
```
No `sys.modules`/`sys.path`/pyc dependency; the executed file is provably `worker/simserver/temp.py`.
Combat rules untouched.

## Layer-3 identity instrumentation (read-only)
`adaptation.build_simulation` writes `RUNTIME_IDENTITY_FILE` = {strategy_filename, formation_mode,
route_digest (canonical SHA-256 of the loaded blue-waypoints), area_digest, pid}. The gate compares
`route_digest` against the frozen route JSON's digest.
