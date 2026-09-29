# BLACK_POLICY_CONTRACT.md — current Black opponent interface (v1)

Recovered from `opponent_profiles.py` + `hsystem/sim_script/20250819TZB/scenario_builder.py`.

## How Black is instantiated
- Entry: `scenario_builder.build_scenario(..., black_movement=<mode>, opponent_profile=<name>, rw_seed=<seed>, ...)`.
- `opponent_profiles.py` provides PURE path generators:
  - `_random_waypoint_paths(seed, ys)`  (B0)
  - `spatial_groups(ys, capacity)` + `_multi_axis_paths(seed, ys, enemy_x, break_x)`  (B1)
  - `_coordinated_pressure_paths(seed, ys, enemy_x, break_x)`  (B2)
  - B3 adaptive: runtime legal controller over Black's own radar intel.
- Black units are driven by `WaypointsMotor` (waypoint list per Black USV).

## Contract items (each external opponent must be checked against these)
| item | requirement |
|------|-------------|
| init inputs | seed, Black unit count, Black y-deployment geometry (independent of White count) |
| legal observation | Black may read ONLY its own unit states + `get_black_targets()` (Black radar intel). NEVER White internal state / hidden truth / future waypoints. |
| action interface | waypoint list / heading+speed commands on Black BLUE units |
| scenario/route control | supplied via scenario builder; route artifacts must bind to Black side |
| step function | deterministic pure function of (seed, geometry, legal obs); identical obs ⇒ identical action |
| reset semantics | re-init per episode; no cross-episode state leak |
| terminal handling | inherited from engine (all-killed / breakthrough / time limit) |
| seed propagation | all randomness derived from the scenario seed; no unseeded `random`/`np.random` |

## Fair-play red lines (auto-quarantine if present)
`os.system`, `subprocess`, `socket`, `requests`/network, `shutil.rmtree`/deletes, absolute-path writes,
env mutation, reading engine hidden state, reading future route truth.
