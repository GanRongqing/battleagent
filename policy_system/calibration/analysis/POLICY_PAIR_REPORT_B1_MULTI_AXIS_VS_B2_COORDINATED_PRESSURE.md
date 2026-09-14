# B1 vs B2

## Declared Semantics

- B1 (B1_MULTI_AXIS): spatial multi-axis groups, local structure
- B2 (B2_COORDINATED_PRESSURE): coordinated pressure, shared timetable

## Artifact Difference

- distinct artifact bundles (sealed, unique hashes)

## Common Calibration

- White frozen W5; S2; same seeds 7001-7010; same instrumentation cal-v1
- episodes: B1 n=10, B2 n=10
- behavioral distance = 0.3710
- response distance = 0.4140

## Behavioral Top Differences (shared available/proxy features)

| feature | mean a | mean b | Cohen's d | direction consistency |
|---|---|---|---|---|
| spatial.mean_group_spacing_km | 84615.6 | 91921.1 | 1.147 | 0.7 |
| temporal.resolution_time | 29449.6 | 26145.0 | -0.892 | 0.3 |
| spatial.visible_window_start_s | 1950.2 | 1980.3 | 0.562 | 0.5 |
| spatial.peak_simultaneous_visible | 17.7 | 18.5 | 0.476 | 0.6 |
| coordination.approach_bearing_entropy | 1.1781 | 1.2297 | 0.38 | 0.6 |

Note: features are available/proxy only; unavailable features are excluded, never 0.
Direction consistency = fraction of the 10 paired seeds where b>a.

Top effect: spatial.mean_group_spacing_km (d=1.147, seed consistency=0.7)

## Response Signature Difference

| feature | mean a | mean b | Cohen's d |
|---|---|---|---|
| outcomes.white_friendly_losses | 11.3 | 7.4 | -1.053 |
| outcomes.white_reacquire_count | 3.5 | 2.3 | -0.525 |
| outcomes.explored_ratio | 0.5167 | 0.5325 | 0.379 |
| outcomes.breakthrough_count | 0.9 | 0.8 | -0.211 |
| outcomes.enemy_kills | 15.1 | 15.2 | 0.051 |
| outcomes.clean_win | 0.0 | 0.0 | 0.0 |

Response = White outcome under the opponent, kept separate from behavior.

## Multi-Seed Stability

- stability basis: direction_consistency on top behavioral effects -> status **unstable**

## Final Verdict

**INCONCLUSIVE**
