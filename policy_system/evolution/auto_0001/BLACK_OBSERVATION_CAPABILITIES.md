# Black Legal Observation Capabilities (read-only audit)

Sources available to a Black policy at runtime (verified in code):
- `engine.get_black_targets()` (hsystem/simulation/core/engine.py:274) -> names of White units
  that any BLUE unit currently holds intel on (`get_intel_targets`). Legal Black radar intel.
- `engine.unit_by_name(name).coords` / `.velocity` / `.isactive` -> own/observed unit state.
- `engine.units()` filtered by `group == "BLUE"` -> Black own ships/UAVs and their positions.
- `engine.get_unit(name)` -> own unit handle for issuing `cmd_sail_area` / `black_cmd_lock`.
- Black UAV (AEW) is recon-only; there is no Black UAV weapon path (physics unchanged).

`opponent_profiles.observe_black(engine)` already packages exactly this:
  {"black_ships": [{name, position, alive}...], "detected_white": {name: [x,y]...}}
It contains NO White hidden state (tracks/allocator/assignments/future actions).

What Black CANNOT legally see (and the new policy must not use):
- White internal tracks, allocation, intent, doctrine, commander state.
- White units outside Black radar intel.
- Future truth, seed-conditioned White behavior, W5/W6/W7 internal version IDs.

Consequence for Feint-and-Switch:
- Feint axis is chosen from Black's own initial geometry + reproducible seed (legal).
- Response trigger uses ONLY `detected_white` (positions of White units Black can see near the
  feint axis) and Black own state.
- Switch/main-push geometry uses own state + detected_white; no White hidden truth.
- Timeout fallback is a bounded deterministic function of sim-time, not of hidden state.
