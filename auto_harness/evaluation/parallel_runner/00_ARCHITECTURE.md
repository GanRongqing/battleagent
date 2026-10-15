# 00 — PARALLEL EVALUATION RUNNER — ARCHITECTURE

## Goal
Episode-level multi-process evaluation: maximise valid episodes/hour on the container's REAL CPU quota,
with bit-identical determinism vs the serial runner and full per-episode isolation.

## Components
- `resource_detector.py` — container-aware CPU/mem detection + `max_safe_workers`.
- `worker_runtime.py` — one isolated Worker = private base_server + sim_server + FastAPI + agent.
- `job_registry.py` — persistent job registry (PENDING/RUNNING/SUCCEEDED/INVALID/RETRYING/FAILED) + resume.
- `result_aggregator.py` — single-writer CSV aggregation (E2-compatible schema).
- `parallel_runner.py` — scheduler (bounded `multiprocessing.Pool`, dynamic work-stealing), CLI.

## Flow
```
parallel_runner (scheduler)
  -> build_jobs(Strategy x Policy x Seed + Epoch/EngineHash/ScenarioHash)
  -> JobRegistry (resume: skip SUCCEEDED)
  -> mp.Pool(workers, initializer=_init)          # each child starts its own isolated Worker
        child i: base_server(:6010+10i) + sim_server + FastAPI(:8010+10i), private seed.txt/api_logs/cwd
        _run_job(job): write seed -> /stop -> agent -> parse [META] + game log -> result JSON
  -> result_aggregator.aggregate (parent only)
```
A free worker immediately takes the next job (`imap_unordered`, chunksize=1) — no batch barriers.

## Isolation (no shared mutable state)
| resource | isolation |
|---|---|
| CPU quota | cgroup v2 `cpu.max` = 9 (host 96 ignored) |
| ports | base=`6010+10w`, sim=`base+1`, api=`8010+10w`, conflict-checked |
| seed file | `worker/seed.txt` via `RW_SEED_FILE` (no global seed file) |
| `sim_server` temp.py | private cwd symlink-farm (`worker/simserver/`) |
| `base_server` temp1.py | private cwd (same farm) |
| FastAPI game/runtime logs | `API_LOG_DIR=worker/api_logs` (main.py override) |
| code / assets | shared read-only via symlinks |

## Non-goals / frozen
ACE, C7, Black strategies, TrackManager, ThreatAllocator, USVController, ActionSafety, sensor/lock/fire
legality, Locker probability semantics, engine stepping, seed plumbing semantics — all unchanged.
