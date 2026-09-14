# B0-v2 Speed Capability Audit (READ-ONLY)

## Speed control chain
1. `scenario_builder.build_scenario` commands Black combat USVs with
   `engine.cmd_sail_area(_b, speed=10, xy_points=_rw_paths[i-1])` (B0 path).
2. `cmd_sail_area` stores the waypoint plan with a per-segment speed; the driver
   (`simulation/arsenal/driver.py`) calls `MotorTZB.change_speed(...)`.
3. `simulation/arsenal/tzb_motor.py`: `set_target_speed(speed)` sets
   `target_speed = max(speed, 0)`; each tick `real_speed` ramps toward target by
   `max_acce`, then `real_speed = clamp(real_speed, -max_speed, +max_speed)`.

## Limits (from database)
- `simulation/database/json/motor.json` -> `ShipMotorTZB`:
  - `max_speed = 10` m/s  (physics/controller cap)
  - `max_acce = 2` m/s^2
  - `period = 0.1` s
- `PlaneMotorTZB` (Black UAV, excluded from formation): `max_speed = 150`.

## Answers
- Where does 10 m/s come from? It is the **hardcoded B0 policy command** AND it
  equals the **physics max_speed** (`ShipMotorTZB.max_speed = 10`). B0-v1 commands the cap.
- Legal Black combat USV speed range: **0 .. 10 m/s** (target_speed clamped >=0; real_speed
  clamped to +/-max_speed). Speeds >10 are physically impossible (clamped).
- Commanded vs actual: actual follows target with acceleration limit 2 m/s^2 and cap 10.

## Selected operational range for B0-v2
`Uniform(5.0, 10.0)` m/s (0.5x .. 1.0x nominal).
Rationale: keeps the attack/breakthrough identity (>= half nominal speed), stays strictly
within the legal range, avoids meaningless near-zero crawl speeds, and preserves the
existing B0 waypoint logic. The upper bound equals the physics cap; the lower bound is a
documented safe operational floor, not a physics limit.
UAV speed is NOT changed (Black UAV is recon-only and excluded from length/width/speed).
