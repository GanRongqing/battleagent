# 00 — Timing Architecture (why same-seed is not reproducible)

## Path
```
agent_hybrid_v5.py run() -> client.apply() -> POST /apply (pomdp_api/main.py)
  -> _state.release_until_time = <logical target>          # our fix
  -> sim_server: engine.update() runs in a thread (CONTINUOUS, _step_end_tick=inf)
       base_engine.pyx update loop:
         _upper_tick = begin_sim + (time.time()*1000 - begin_real) * _ratio   (:987)
         if next_event.when <= _upper_tick: execute_event  else: sleep(...)   (:1062)
```

## Answers
1. **Engine continuous advance**: `sim_server.py:279` starts `engine.update()` (no delta) in a thread
   => `_step_end_tick = inf` => it never stops at a step boundary.
2. **sim_time variable**: `self._tick` (ms), advanced by executing cron events; exposed as `.time`.
3. **wall-clock throttle**: `_upper_tick = begin_sim + elapsed_wall * ratio` + `time.sleep((when-upper)/1000/ratio)`.
4. **/apply**: sets `_state.release_until_time` (an API-level target); it does NOT stop the engine.
5. **current+30**: `pomdp_api/main.py` /apply — replaced by the logical clock (`logical_release_until += 30`).
6. **logical_release_until**: makes the API-level target deterministic (t0 + n*30), removing CUMULATIVE drift.
7. **why not exact**: the engine keeps advancing continuously; the observed sim_time = the engine time at
   the poll instant = target + (wall-clock-dependent overshoot).
8. **overshoot**: observed earlier `1,33,63,93...` (target 31,61,91 => overshoot +2..+4, varying).
9. **pause/apply/advance/pause**: POSSIBLE — the engine already exposes `update(delta)` (advance exactly
   `delta` s then break) and `stop_update()`/`restart_update()`. `sim_server` uses neither.

## Root cause of residual non-determinism
The engine advances continuously throttled by wall-clock; observations are samples of that continuous
advance. So even with a deterministic release TARGET, the sampled STATE differs per run. Exact same-seed
reproducibility requires **step mode**: pause, apply, advance exactly Δ (via `update(delta)`), pause,
read — never sampling a moving engine.
