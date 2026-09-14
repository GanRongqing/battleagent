# B0 vs B2

## Declared Semantics

- B0 (B0_RANDOM): random waypoints, low coordination
- B2 (B2_COORDINATED_PRESSURE): coordinated pressure, shared timetable

## Artifact Difference

- distinct artifact bundles (sealed, unique hashes)

## Common Calibration

- White frozen W5; S2; same seeds 7001-7010; same instrumentation cal-v1
- episodes: B0 n=10, B2 n=10
- behavioral distance = 1.1760
- response distance = 1.2560

## Behavioral Top Differences (shared available/proxy features)

| feature | mean a | mean b | Cohen's d | direction consistency |
|---|---|---|---|---|
| spatial.mean_group_spacing_km | 33820.4 | 91921.1 | 9.821 | 1.0 |
| spatial.visible_pairwise_dist_km_median | 28.9701 | 76.1224 | 6.951 | 1.0 |
| spatial.visible_y_spread_km_median | 86.7116 | 178.0419 | 4.831 | 1.0 |
| coordination.approach_bearing_entropy | 0.6365 | 1.2297 | 3.541 | 1.0 |
| spatial.approach_lane_entropy | 0.6365 | 1.2297 | 3.541 | 1.0 |

Note: features are available/proxy only; unavailable features are excluded, never 0.
Direction consistency = fraction of the 10 paired seeds where b>a.

Top effect: spatial.mean_group_spacing_km (d=9.821, seed consistency=1.0)

## Response Signature Difference

| feature | mean a | mean b | Cohen's d |
|---|---|---|---|
| outcomes.victory | 1.0 | 0.0 | -1000000000.0 |
| outcomes.clean_win | 0.9 | 0.0 | -4.243 |
| outcomes.enemy_kills | 19.9 | 15.2 | -3.687 |
| outcomes.explored_ratio | 0.3766 | 0.5325 | 2.599 |
| outcomes.breakthrough_count | 0.1 | 0.8 | 1.476 |
| outcomes.white_friendly_losses | 6.2 | 7.4 | 0.284 |

Response = White outcome under the opponent, kept separate from behavior.

## Multi-Seed Stability

- stability basis: direction_consistency on top behavioral effects -> status **stable**

## Final Verdict

**EMPIRICALLY_DISTINCT**
