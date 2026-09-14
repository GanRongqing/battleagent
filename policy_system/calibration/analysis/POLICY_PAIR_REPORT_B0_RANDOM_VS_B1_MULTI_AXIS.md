# B0 vs B1

## Declared Semantics

- B0 (B0_RANDOM): random waypoints, low coordination
- B1 (B1_MULTI_AXIS): spatial multi-axis groups, local structure

## Artifact Difference

- distinct artifact bundles (sealed, unique hashes)

## Common Calibration

- White frozen W5; S2; same seeds 7001-7010; same instrumentation cal-v1
- episodes: B0 n=10, B1 n=10
- behavioral distance = 1.2690
- response distance = 1.5260

## Behavioral Top Differences (shared available/proxy features)

| feature | mean a | mean b | Cohen's d | direction consistency |
|---|---|---|---|---|
| spatial.mean_group_spacing_km | 33820.4 | 84615.6 | 8.988 | 1.0 |
| spatial.visible_pairwise_dist_km_median | 28.9701 | 73.5297 | 8.1 | 1.0 |
| spatial.visible_y_spread_km_median | 86.7116 | 181.3669 | 5.537 | 1.0 |
| coordination.approach_bearing_entropy | 0.6365 | 1.1781 | 3.437 | 1.0 |
| spatial.approach_lane_entropy | 0.6365 | 1.1781 | 3.437 | 1.0 |

Note: features are available/proxy only; unavailable features are excluded, never 0.
Direction consistency = fraction of the 10 paired seeds where b>a.

Top effect: spatial.mean_group_spacing_km (d=8.988, seed consistency=1.0)

## Response Signature Difference

| feature | mean a | mean b | Cohen's d |
|---|---|---|---|
| outcomes.victory | 1.0 | 0.0 | -1000000000.0 |
| outcomes.clean_win | 0.9 | 0.0 | -4.243 |
| outcomes.enemy_kills | 19.9 | 15.1 | -3.172 |
| outcomes.breakthrough_count | 0.1 | 0.9 | 2.667 |
| outcomes.explored_ratio | 0.3766 | 0.5167 | 2.55 |
| outcomes.white_friendly_losses | 6.2 | 11.3 | 2.262 |

Response = White outcome under the opponent, kept separate from behavior.

## Multi-Seed Stability

- stability basis: direction_consistency on top behavioral effects -> status **stable**

## Final Verdict

**EMPIRICALLY_DISTINCT**
