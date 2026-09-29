# 04 — Root-cause trace: residual state non-determinism

## Symptom
Under `DETERMINISTIC_STEP_MODE`, macro-step sim-times were exactly reproducible (`[0,30,60,...]`)
but the step-1 state hash diverged.

## Investigation (bounded pass)
1. Captured 3 same-seed runs at t=0/30/60 (`traces/`), flattened to `{(entity, field): value}`.
2. `01_FIRST_DIVERGENCE.json`: **t=0 identical**; t=30 → 12 differing fields over
   `white_usv3`, `white_usv5`, `white_usv6`; **first field = `white_usv3.course`**
   (run0=0.0, run1=0.0, run2=90.0).
3. The commanded action was `legal_actions["[move]"][0]`. Inspecting the raw snapshot showed the
   `white_usv_states` **list order differs every run**:
   - run0: `white_usv6, white_usv9, white_usv12, ...`
   - run1: `white_usv5, white_usv8, white_usv1, ...`
   - run2: `white_usv3, white_usv2, white_usv7, ...`
   → `[move][0]` addressed a **different USV** each run, so the trajectories diverged.

## Confirmation that physics itself is deterministic
Re-running with a **fixed, order-independent action text** (`white_usv1 移动 ...`) produced
t=0/30/60 states **identical by name** across all 3 runs (`diff_counts = {0:0, 30:0, 60:0}`).
So the engine physics/RNG were already deterministic; the only non-determinism was **ordering**.

## Root cause
`hsystem/simulation/arsenal/judge_system.py:45-47`:
```python
def set_units(self, units):
    self.units = set(units)
    self.units_all = self.units.copy()   # <-- set: iteration order = object hashes (id-based)
```
`self.units_all` is iterated by `engine.get_state()` (builds `white_usv_states`) and `tzb_engine`/
judge loops. Python set iteration order over objects is derived from `id()` (memory address), which
varies per process → the readout order (and therefore any order-dependent consumer incl. the agent's
action selection) varied run-to-run. **This is a pure ordering issue, not physics/RNG.**

## Write chain
`set_units` (builds `units_all`) → `engine.get_state` (`for unit in self.judge.units_all` → appends
`white_usv_states`) → `/status` (+ `/legal_actions` order) → agent action selection.
No RNG draw, cron timestamp, or entity creation order was involved.
