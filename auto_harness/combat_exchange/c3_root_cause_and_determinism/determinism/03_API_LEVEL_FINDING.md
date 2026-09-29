# 03 — API-level Determinism Attempt: PARTIAL (insufficient)

## What was tried
Added an opt-in flag `DETERMINISTIC_STEP_MODE` (default **off**) in `hsystem/pomdp_api/main.py`:
when true, `/apply` **blocks** after setting its logical release target until the sim server's
authoritative engine time actually reaches that target. Intended to make each macro-step boundary
exact so the next `/status` samples a fixed sim-time.

## Code
- `main.py:96-98` — `DETERMINISTIC_STEP_MODE = os.getenv(...)`.
- `main.py:234` — `EpisodeState.actual_obs_tick`.
- `main.py:1823-1838` — in `/apply`, after `_record_step`, block-poll `_fetch_raw_state()` until
  `_r2(raw["time"]) >= release_until_time` (deadline `max(30, 2*MACRO_STEP)`).

## Result (same seed 11001, scenario S1, 30 steps, 3 repeats, mode ON)
| run | abs_t @ steps 0-3 | rel_t (t[i]-t[0]) steps 0-5 |
|-----|-------------------|------------------------------|
| 0 | 1, 35, 67, 96 | 0, 34, 66, 95, 127, 154 |
| 1 | 1, 38, 68, 96 | 0, 37, 67, 95, 126, 158 |
| 2 | 2, 37, 66, 96 | 0, 35, 64, 94, 125, 154 |

`first_hash_divergence = step 1` for both pairs → **STILL DIVERGED**.

## Why it fails
`/apply` waits for the engine to *cross* the release target, but the engine **does not stop there** —
it keeps advancing (wall-clock-throttled continuous `engine.update()` at `sim_server.py:279`). By the
time the next `/status` reads it, 1–4 sim-sec of extra advance have occurred. This residual boundary
overshoot is enough to break hash equality at step 1. The variance is reduced (was ±5–6, now ±3) but
not eliminated: **an API-layer wait cannot fix an engine that never stops.**

## Conclusion
Determinism requires the **engine to be paused at exact boundaries** — i.e. an engine/sim-server-level
step mode (`engine.update(delta=MACRO_STEP)` → `engine.stop_update()` → wait → `restart_update()`),
not an API-layer wait. See `00_TIMING_ARCHITECTURE.md` §proposed for the design.

Flag left in place, **default OFF**, so production behaviour is unchanged.
