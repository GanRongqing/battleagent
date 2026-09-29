# DETERMINISM_RESULT.md — Stage A final

## Verdict: **SOLVED**

## Summary
| item | value |
|------|-------|
| macro-step timing | DETERMINISTIC (`[0,30,60,...]`) |
| first state divergence (before fix) | t=30, `white_usv3.course` (+ usv5/usv6) |
| root cause | `set` iteration order in `judge_system.set_units` (`units_all`) |
| fix applied | YES (sort `units_all` by name) |
| 3-run step hashes identical | YES (30 macro-steps) |
| normal mode affected | NO |
| same seed semantics | **strict paired trajectory initial condition** (physics deterministic) |

## Detail
1. Macro-step mode gave exact sim-times but step-1 state hash diverged.
2. Field/entity diff (`01_FIRST_DIVERGENCE.json`) localised the first difference to
   `white_usv3.course` at t=30; the raw snapshot showed `white_usv_states` **ordering** differed each run.
3. With a fixed (order-independent) action the states were identical → engine physics/RNG are
   deterministic; only ordering was not.
4. Root cause = `self.units = set(units)` → `units_all` iteration order derived from object
   `id()` (varies per process).
5. Fix = `self.units_all = sorted(self.units, key=lambda u: getattr(u, "name", ""))`.
6. Re-test: 3×30-step order-dependent runs → STATE-IDENTICAL.

## Consequence for Stage B
- Because physics + ordering are now deterministic, **same seed = strict paired trajectory initial
  condition** (not merely a seed-matched block). Stage B may still report paired-seed honestly.

## Notes / limits
- Verified over 30 macro-steps (900 s) on S1; not a full-episode proof, but the ordering fix is
  global and the divergence source was process-scoped, not time-scoped.
- The fix touches the simulator core (`judge_system.py`) but only reorders an iteration; no physics,
  sensing, weapon, agent, scenario, or timing semantics changed.
