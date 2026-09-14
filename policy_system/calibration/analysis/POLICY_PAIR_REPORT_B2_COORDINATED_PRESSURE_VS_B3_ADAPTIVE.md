# B2 vs B3

## Declared Semantics

- B2 (B2_COORDINATED_PRESSURE): coordinated pressure, shared timetable
- B3 (B3_ADAPTIVE): B2-like coordination + legal-observation-driven adaptation

## Artifact Difference

- distinct artifact bundles (sealed, unique hashes)

## Common Calibration

- White frozen W5; S2; same seeds 7001-7010; same instrumentation cal-v1
- episodes: B2 n=10, B3 n=10
- behavioral distance = 1.1110
- response distance = 0.9770

## Behavioral Top Differences (shared available/proxy features)

| feature | mean a | mean b | Cohen's d | direction consistency |
|---|---|---|---|---|
| adaptation.dispersion_event_count | 0.0 | 196.0 | 11.181 | 1.0 |
| adaptation.lane_shift_count | 0.0 | 235.2 | 9.999 | 1.0 |
| adaptation.adaptive_replan_count | 0.0 | 619.7 | 7.613 | 1.0 |
| adaptation.detected_white_event_count | 0.0 | 1097.5 | 4.973 | 1.0 |
| spatial.mean_visible_group_count | 3.97 | 4.87 | 2.845 | 1.0 |

Note: features are available/proxy only; unavailable features are excluded, never 0.
Direction consistency = fraction of the 10 paired seeds where b>a.

Top effect: adaptation.dispersion_event_count (d=11.181, seed consistency=1.0)

## Response Signature Difference

| feature | mean a | mean b | Cohen's d |
|---|---|---|---|
| outcomes.victory | 0.0 | 0.9 | 4.243 |
| outcomes.enemy_kills | 15.2 | 19.5 | 3.201 |
| outcomes.clean_win | 0.0 | 0.6 | 1.732 |
| outcomes.white_reacquire_count | 2.3 | 4.6 | 1.026 |
| outcomes.breakthrough_count | 0.8 | 0.4 | -0.73 |
| outcomes.white_friendly_losses | 7.4 | 8.5 | 0.232 |

Response = White outcome under the opponent, kept separate from behavior.

## Multi-Seed Stability

- stability basis: direction_consistency on top behavioral effects -> status **stable**

## Final Verdict

**EMPIRICALLY_DISTINCT**
