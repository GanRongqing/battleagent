# AUTO_POLICY_MULTI_SCENARIO_VALIDATION — black-auto-0001-v1 vs B0

Candidate and reference B0 both run on fresh DEV seeds 7201-7205.
S1 = White 5+5 vs Black 10; S3 = White 15+15 vs Black 30.

## S1

- candidate N = 5, reference N = 5
- behavior distance = 1.353
- verdict = EMPIRICALLY_DISTINCT

| feature | mean cand | mean ref | Cohen's d | seed consistency |
|---|---|---|---|---|
| structure.early_force_commitment_ratio | 0.04 | 0.44 | 8.165 | 1.0 |
| structure.early_late_concentration_delta | 0.16 | 0.56 | 8.165 | 1.0 |
| spatial.mean_visible_group_count | 2.32 | 2.8 | 1.947 | 0.8 |

## S3

- candidate N = 5, reference N = 5
- behavior distance = 1.439
- verdict = EMPIRICALLY_DISTINCT

| feature | mean cand | mean ref | Cohen's d | seed consistency |
|---|---|---|---|---|
| structure.early_force_commitment_ratio | 0.0734 | 0.4867 | 13.868 | 1.0 |
| structure.early_late_concentration_delta | 0.1266 | 0.5133 | 12.975 | 1.0 |
| spatial.mean_visible_group_count | 7.02 | 7.84 | 1.881 | 0.8 |

## Core signature preservation (direction consistency by scenario)

| core feature | S1 | S3 |
|---|---|---|
| structure.reserve_fraction | None | None |
| structure.role_asymmetry_index | None | None |
| structure.dominant_axis_shift_count | None | None |
| structure.phase_switch_count | None | None |
| structure.continuous_replan_count | None | None |

multi_scenario_validated = YES
