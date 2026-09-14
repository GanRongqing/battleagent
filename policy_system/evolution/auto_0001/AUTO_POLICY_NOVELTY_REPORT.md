# AUTO_POLICY_NOVELTY_REPORT — black-auto-0001-v1 vs B0-B3 (S2, 7001-7010)

nearest existing policy = B0_RANDOM (behavior distance 1.27)

| reference | behavior distance | response distance | top feature | Cohen's d | seed consistency | verdict |
|---|---|---|---|---|---|---|
| B0_RANDOM | 1.27 | 0.413 | structure.early_late_concentration_delta | 5.052 | 1.0 | EMPIRICALLY_DISTINCT |
| B1_MULTI_AXIS | 1.479 | 1.257 | structure.early_late_concentration_delta | 6.099 | 1.0 | EMPIRICALLY_DISTINCT |
| B2_COORDINATED_PRESSURE | 1.384 | 1.112 | spatial.mean_group_spacing_km | 4.221 | 1.0 | EMPIRICALLY_DISTINCT |
| B3_ADAPTIVE | 1.435 | 0.425 | adaptation.dispersion_event_count | 11.181 | 1.0 | EMPIRICALLY_DISTINCT |

Generic fp-v3 structural features (uniform for all policies):
reserve_fraction, early/late commitment ratios, role_asymmetry_index, dominant_axis_shift_count, phase_switch_count, continuous_replan_count.