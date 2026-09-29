# 05 — Engine step mode: implemented, timing EXACT, state still divergent

## What was implemented (opt-in `DETERMINISTIC_STEP_MODE`, default OFF)
Reuses the framework's existing generic `control` dispatch (sim_server forwards unknown `func_name`
to `engine.<func>`), so **no proto / gRPC change** was needed:
- `_do_init`: `init(update=False)` → engine created **paused**.
- after init: `set_ratio_inf()` → `_ratio="SYSTEM"` ⇒ `_upper_tick=inf` (no wall-clock cap).
- `/apply`: `update(delta=MACRO_STEP)` advances **exactly** one macro-step, then samples; the
  engine stops at `_step_end_tick` (`base_engine.pyx:1020`).
- `/stop`: after `terminate`, one `update(delta=1)` tick so the loop raises `SimStop` → `kill()` →
  `isactive=False` (otherwise the heartbeat reports RUNNING and the next `/start` fails).

## Result (same seed 11001, S1, 30 steps, 3 episodes in one process)
```
run 0: abs_t=[0,30,60,90,...]  rel_t=[0,30,60,90,120,150]
run 1: abs_t=[0,30,60,90,...]  rel_t=[0,30,60,90,120,150]
run 2: abs_t=[0,30,60,90,...]  rel_t=[0,30,60,90,120,150]
first_rel_time_divergence = None   <-- TIMING NOW EXACT / REPEATABLE
first_hash_divergence     = 1      <-- STATE STILL DIVERGES
```

## Interpretation
- **Macro-step timing is fully deterministic** now (was ±3–6 s drift; now exactly n*30). This is a
  real improvement: boundary sampling variance is gone.
- **State at step 1 still differs** despite identical sim-time. So there is a residual non-determinism
  *inside the engine's first 30 s* independent of wall-clock gating. Candidates (not yet isolated):
  1. RNG not reseeded/independent of the seed file at per-unit spawn (radar/weapon jitter, red
     formation randomness).
  2. Action (`send_command`) applied at a slightly different engine tick / to a different target.
  3. Floating-point message ordering tie-break in `_cron` (same tick, non-stable order).

## Status
- Determinism verdict: **IMPROVED_NOT_SOLVED**. Timing solved; state residual remains.
- Flag default OFF → production/graded behaviour unchanged (verified: normal-mode start/apply/stop OK).
- Kept as an opt-in foundation for a future RNG/ordering audit; **not** used for candidate evaluation.

## Next (deferred)
Audit engine RNG seeding + `_cron` tie-break order. If those are the cause, single-seed diagnostics
become viable. Until then, keep using paired fresh seeds for candidate evaluation.
