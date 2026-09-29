# 02 — Determinism Report

## What was already done
`logical_release_until` in `pomdp_api/main.py`: the /apply release target is now a logical clock
(`t0 + n*MACRO_STEP`) instead of `engine_current + MACRO_STEP`. This removes **cumulative drift**.

## What is still non-deterministic
The engine runs **continuously** (`sim_server.py:279` -> `engine.update()` no delta); the API samples
its state. So the observed sim_time = target + a wall-clock-dependent overshoot (2-4 s observed), which
varies per run. => same seed still gives different trajectories.

## Deterministic mode design (DETERMINISTIC_STEP_MODE)
The engine already provides the primitives (`base_engine.pyx`): `update(delta)` (advance exactly `delta`
seconds then `break`, setting `_tick = _step_end_tick`), `stop_update()`, `restart_update()`.
Proposed (MINIMAL, scheduler-level only; no physics change):
1. sim_server, when `DETERMINISTIC_STEP_MODE=1`, does NOT start the continuous thread; instead it
   exposes a step call: on each API `/apply`, call `engine.update(delta=MACRO_STEP)` (advance exactly 30
   sim-s) and then `engine.stop_update()` (pause), then return.
2. The API's `/apply` (or a new gRPC "advance_until") triggers the step; `/status` reads only while paused.
3. property to add: `engine.advance_until(target_tick)` = loop `update` until `_tick == target_tick`
   (or clamp to it), guaranteeing the observation tick equals the logical target.

## Constraint compliance (design)
- Not changed: physics, radar, legality, weapon, terminal condition.
- Only changed: WHEN the engine advances and when the observation is read (scheduler).
- production mode unchanged; opt-in via env flag.

## Status
- Analysis: COMPLETE.
- Implementation: NOT DONE this round (would require a `sim_server.py` scheduler change + re-test).
- Verdict: **DETERMINISM_IMPROVED (drift removed) but NOT SOLVED (continuous sampling remains)**.
- Full determinism requires the `advance_until` step mode above.
