# B1 vs B3

## Declared Semantics

- B1 (B1_MULTI_AXIS): spatial multi-axis groups, local structure
- B3 (B3_ADAPTIVE): B2-like coordination + legal-observation-driven adaptation

## Artifact Difference

- distinct artifact bundles (sealed, unique hashes)

## Common Calibration

- White frozen W5; S2; same seeds 7001-7010; same instrumentation cal-v1
- episodes: B1 n=10, B3 n=10
- behavioral distance = 1.1000
- response distance = 1.0060

## Behavioral Top Differences (shared available/proxy features)

| feature | mean a | mean b | Cohen's d | direction consistency |
|---|---|---|---|---|
| adaptation.dispersion_event_count | 0.0 | 196.0 | 11.181 | 1.0 |
| adaptation.lane_shift_count | 0.0 | 235.2 | 9.999 | 1.0 |
| adaptation.adaptive_replan_count | 0.0 | 619.7 | 7.613 | 1.0 |
| adaptation.detected_white_event_count | 0.0 | 1097.5 | 4.973 | 1.0 |
| spatial.mean_visible_group_count | 3.86 | 4.87 | 4.016 | 1.0 |

Note: features are available/proxy only; unavailable features are excluded, never 0.
Direction consistency = fraction of the 10 paired seeds where b>a.

Top effect: adaptation.dispersion_event_count (d=11.181, seed consistency=1.0)

## Response Signature Difference

| feature | mean a | mean b | Cohen's d |
|---|---|---|---|
| outcomes.victory | 0.0 | 0.9 | 4.243 |
| outcomes.enemy_kills | 15.1 | 19.5 | 2.8 |
| outcomes.clean_win | 0.0 | 0.6 | 1.732 |
| outcomes.breakthrough_count | 0.9 | 0.4 | -1.231 |
| outcomes.white_friendly_losses | 11.3 | 8.5 | -0.898 |
| outcomes.white_reacquire_count | 3.5 | 4.6 | 0.37 |

Response = White outcome under the opponent, kept separate from behavior.

## Multi-Seed Stability

- stability basis: direction_consistency on top behavioral effects -> status **stable**

## Final Verdict

**EMPIRICALLY_DISTINCT**
