# AUTO_POLICY_DESIGN — black-auto-0001-v1 (FEINT_SWITCH_V1)

- Strategy family: feint_and_switch
- Declared intent: manufacture an incorrect White resource response with a small feint,
  then shift the main effort to a second legal pressure axis (phased pressure transfer,
  delayed main-force commitment, reserve usage).
- Parent policy: null (independent implementation; does not derive from B0-B3 helpers).

## Phases
INIT -> FEINT -> OBSERVE_RESPONSE -> SWITCH -> MAIN_PUSH -> DEGRADED
(INIT is the t=0 state before the first manipulator call; FEINT is the first observed phase.)

## Group roles (scale-agnostic)
- feint = max(1, round(0.20 n)); reserve = round(0.15 n) if n>=5 else 0; main = remainder.
- n=3 -> 1/2/0 ; n=10 -> 2/7/1 ; n=20 -> 4/13/3 ; n=30 -> 6/19/5 ; n=50 -> 10/32/8.

## Triggers
- RESPONSE_TRIGGER: >= RESPONSE_MIN_WHITE (2) detected White units within RESPONSE_RADIUS
  (60 km) of the feint axis, from `get_black_targets()` (legal radar intel).
- TIMEOUT_SWITCH: if no legal response by FEINT_TIMEOUT (7000 sim-s) -> deterministic fallback.
- FEINT_ATTRITION: feint group alive fraction < 0.34 -> early switch.
- RESERVE_COMMIT: one-time when main-force centroid x <= COMMIT_X (180 km).
- DEGRADED: main-force alive fraction < 0.34 -> stop re-planning, keep last orders.

## Legal observations used
`observe_black`: Black own ship states + detected White positions from `get_black_targets()`.
No White hidden state, no version/seed special-casing, no future truth. UAVs are recon-only.

## Fallback / damage response
Timeout gives a bounded fallback main push; attrition triggers early push; heavy main loss
degrades pressure without switching to another doctrine (family identity preserved).

## Variable-cardinality rule
Role counts from fixed fractions with bounded minima; no per-count branches.

## Expected empirical signature (to be tested, not assumed)
- phase_switch_count > 0 (2-3) vs 0 for B0/B1/B2 and high-frequency for B3.
- low continuous replanning (replan_count ~ few) vs B3 ~620.
- reserve_fraction / role asymmetry > 0 vs ~0 for B0-B3.
- early low commitment -> late concentrated main push (early/late commitment delta).
- dominant-axis shift between feint axis and main axis.

## Expected weakness
If White does not over-commit to the feint, the feint wastes time; discrete switch can raise
resolution; delayed main commitment can reduce early pressure.

## Nearest expected neighbor
B2 (coordinated pressure) / B3 (adaptive) — must be tested, not assumed.

## Why not duplicate
B0-B3 never hold a reserve or use a phased discrete switch; B3 switches continuously, not
in a few phases. The role asymmetry + phase structure is a new behavioral quadrant.
