# B0 vs B3

## Declared Semantics

- B0 (B0_RANDOM): random waypoints, low coordination
- B3 (B3_ADAPTIVE): B2-like coordination + legal-observation-driven adaptation

## Artifact Difference

- distinct artifact bundles (sealed, unique hashes)

## Common Calibration

- White frozen W5; S2; same seeds 7001-7010; same instrumentation cal-v1
- episodes: B0 n=10, B3 n=10
- behavioral distance = 1.3350
- response distance = 0.7690

## Behavioral Top Differences (shared available/proxy features)

| feature | mean a | mean b | Cohen's d | direction consistency |
|---|---|---|---|---|
| adaptation.dispersion_event_count | 0.0 | 196.0 | 11.181 | 1.0 |
| adaptation.lane_shift_count | 0.0 | 235.2 | 9.999 | 1.0 |
| adaptation.adaptive_replan_count | 0.0 | 619.7 | 7.613 | 1.0 |
| adaptation.detected_white_event_count | 0.0 | 1097.5 | 4.973 | 1.0 |
| spatial.mean_group_spacing_km | 33820.4 | 59930.9 | 4.724 | 1.0 |

Note: features are available/proxy only; unavailable features are excluded, never 0.
Direction consistency = fraction of the 10 paired seeds where b>a.

Top effect: adaptation.dispersion_event_count (d=11.181, seed consistency=1.0)

## Response Signature Difference

| feature | mean a | mean b | Cohen's d |
|---|---|---|---|
| outcomes.explored_ratio | 0.3766 | 0.5204 | 1.988 |
| outcomes.white_reacquire_count | 1.9 | 4.6 | 0.897 |
| outcomes.enemy_kills | 19.9 | 19.5 | -0.77 |
| outcomes.breakthrough_count | 0.1 | 0.4 | 0.739 |
| outcomes.clean_win | 0.9 | 0.6 | -0.739 |
| outcomes.white_friendly_losses | 6.2 | 8.5 | 0.619 |

Response = White outcome under the opponent, kept separate from behavior.

## Multi-Seed Stability

- stability basis: direction_consistency on top behavioral effects -> status **stable**

## Final Verdict

**EMPIRICALLY_DISTINCT**
