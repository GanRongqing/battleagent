# B0-v2 Design — black-b0-v2 (variable-speed random baseline)

## Why
B0-v1 commands a fixed 10 m/s (= ShipMotorTZB.max_speed), so the 27-class speed axis
is degenerate (28/28 speed LOW; 9 occupied cells). B0-v2 fixes ONLY the speed variance
while preserving the random / uncoordinated / non-adaptive doctrine.

## Immutability
- black-b0-v1 is untouched (same card, artifacts, fp-v1/fp-v2, 28-log stratification).
- black-b0-v2 is a new immutable policy_id, parent = black-b0-v1.

## Speed model
- episode_target_speed ~ Uniform(5.0, 10.0) m/s (audit: legal 0..10; operational 0.5x..1x).
- Sampled once per episode at scenario build, held for the episode.
- Deterministic: random.Random((seed*1000003) ^ 0xB0B2) — a SEPARATE RNG stream, so the
  waypoint RNG (random.Random(seed) inside _random_waypoint_paths) is unchanged.
- Waypoint logic is IDENTICAL to B0-v1 for the same seed.
- No group/lane/target-selection/replan/feint/adaptive logic. No UAV change.

## Integration
scenario_builder: profile token `B0_V2_VARIABLE_SPEED` -> same `_random_waypoint_paths`
as B0, speed = opponent_b0_v2.sample_speed(seed); writes /tmp/opencode/b0v2_meta.json
(requested=effective=black-b0-v2, seed, episode_target_speed). No manipulator registered.

## Classification
Reuse the frozen B0-v1 pipeline definitions (PCA P90-P10 span; episode median actual
combat-USV speed). B0-v2 percentiles are computed INDEPENDENTLY (no v1 thresholds).
