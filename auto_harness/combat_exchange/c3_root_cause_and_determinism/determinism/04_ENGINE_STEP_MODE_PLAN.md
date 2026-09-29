# 04 — Engine-level Deterministic Step Mode: implementation plan

Goal: make macro-step boundaries exact so `same seed + same action sequence ⇒ same state trace`.

## Why API-layer is not enough (evidence)
See `03_API_LEVEL_FINDING.md`: `/apply` can wait for the engine to *cross* the target, but the
engine keeps running, so the next `/status` sees +1..4 sim-sec overshoot → step-1 hash divergence.

## Required change (engine pauses at each boundary)
The engine already exposes everything needed (`base_engine.pyx`):
- `update(int delta)`  (l.955): advances exactly `delta` sim-sec then **returns** (breaks on `_step_end_tick`).
- `stop_update()` (l.935): pauses the update loop.
- `restart_update()` (l.943): resumes.
- `set_ratio_inf()` (l.222): `_ratio="SYSTEM"` ⇒ `_upper_tick=inf` ⇒ no wall-clock throttle
  (otherwise `update(delta)` is still capped by real time — `_upper_tick`, `time.sleep`, `base_engine.pyx:987/1062`).

## Design (opt-in `DETERMINISTIC_STEP_MODE`, default off)
1. `sim_server.py` (~l.279): when the flag is on, replace `threading.Thread(target=engine.update)`
   with a **gated step loop**:
   ```
   engine.set_ratio_inf()                 # deterministic: no wall-clock cap
   while not terminated:
       if not engine._updating:           # paused → wait for resume from API
           time.sleep(0.005); continue
       engine.update(_to_int(MACRO_STEP)) # advance EXACTLY MACRO_STEP, returns
       engine.stop_update()               # PAUSE at the boundary
   ```
2. Resume signal: the API `/apply`, after recording the actions, tells the sim server to take one
   step. Two options:
   - **A (no proto change):** reuse the existing `send_command`/`init(update=True)` path — the API's
     `/apply` already round-trips to the sim server via the base server; have it call the step trigger
     there.
   - **B (clean):** add a `step(delta)` gRPC to `simserver.proto` + base_server forward + client.
   Prefer **A** to keep the change local to `sim_server.py` + the API.
3. Compatibility: with the flag off, keep `threading.Thread(target=engine.update)` — zero behaviour change.

## Verification protocol
- Start one instance with `DETERMINISTIC_STEP_MODE=true` **and** the engine step loop.
- Run `determinism_test_rel.py <port> 3 30` (compares state hashes + relative times).
- Pass criterion: `first_hash_divergence = None` for both repeats (state trace identical).
- Record to `determinism/01_REPEATABILITY.csv`.

## Expected impact if it passes
- Enables small-sample, single-seed candidate evaluation (removes the paired-fresh-seed requirement
  for *diagnostics*; still use fresh seeds for confirmatory claims).
- Does not change production/graded behaviour (flag default off).

## Risk / scope
- Touches simulator scheduling (`sim_server.py`) — a local, flag-gated scheduler change; no change to
  physics/weapon/radar/judge. Allowed only if determinism is judged necessary for the next candidate
  decision (it is: current single-seed results are unusable).
