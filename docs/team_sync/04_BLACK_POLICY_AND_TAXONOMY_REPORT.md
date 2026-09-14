# 04 — Black Policy & Taxonomy Report

## 1. Registered Black policies (strategy_library.db)
| policy_id | family | status | role | parent | bundle_hash (prefix) | entrypoint |
|---|---|---|---|---|---|---|
| black-b0-v1 | random_maneuver | sealed | historical_anchor | – | 4ebdfe5698f8 | scenario_builder random_waypoint |
| black-b0-v2 | random_uncoordinated | validation | historical_anchor | black-b0-v1 | 0ebf9b6e33da | opponent_b0_v2.py |
| black-b1-v1 | multi_axis_penetration | active | general_opponent | – | b5dfd47d30a0 | opponent_profiles.py |
| black-b2-v1 | coordinated_pressure | active | general_opponent | black-b1-v1 | 5834020c78cb | opponent_profiles.py |
| black-b3-v1 | adaptive_multi_axis_penetration | active | stress_test | black-b2-v1 | 74060daae717 | opponent_profiles.py |
| black-auto-0001-v1 | feint_and_switch | active | stress_test | null | 595e0f8bf8be | opponent_auto_profiles.py |

## 2. Empirical classes (taxonomy)
Source: `policy_system/evolution/auto_0001/AUTO_POLICY_TAXONOMY.md`, `b0_v2/B0_V2_TAXONOMY_UPDATE.md`.
| class | signature | members |
|---|---|---|
| E0 Random / Uncoordinated | no phases, low lane entropy, compressed arrival front | black-b0-v1 (fixed-speed), black-b0-v2 (variable-speed) |
| E1 Structured Multi-Axis Pressure | wide dispersion, high lane entropy, structured groups | black-b1-v1, black-b2-v1 |
| E2 Adaptive Replanning Pressure | continuous high-frequency legal replanning | black-b3-v1 |
| E3 Phased Feint-Switch Pressure | small feint + reserve, few discrete switches, low continuous replanning | black-auto-0001-v1 |

## 3. Pairwise empirical verdicts
Source: `policy_system/calibration/analysis/POLICY_DIFFERENCE_MATRIX_V2.csv`,
`policy_system/evolution/auto_0001/POLICY_DIFFERENCE_MATRIX_V3.csv`, `policy_validations`.
| pair | behavior dist | response dist | verdict |
|---|---|---|---|
| B0 vs B1 | 1.269 | 1.526 | EMPIRICALLY_DISTINCT |
| B0 vs B2 | 1.176 | 1.256 | EMPIRICALLY_DISTINCT |
| B0 vs B3 | 1.335 | 0.769 | EMPIRICALLY_DISTINCT |
| B1 vs B2 | 0.371 | 0.414 | **INCONCLUSIVE** |
| B1 vs B3 | 1.100 | 1.006 | EMPIRICALLY_DISTINCT |
| B2 vs B3 | 1.111 | 0.977 | EMPIRICALLY_DISTINCT |
| AUTO1 vs B0/B1/B2/B3 | 1.270 / 1.479 / 1.384 / 1.435 | 0.413 / 1.257 / 1.112 / 0.425 | all EMPIRICALLY_DISTINCT |

> SOURCE CONFLICT: B0-vs-B3 distance appears as 1.2316 (fp-v1, 93 ep) and 1.335 (fp-v2, 10 ep).
> Both are in `policy_validations`; they are different fingerprint versions.

## 4. B0 27-class log stratification (within-policy strata, NOT policies)
Source: `b0_log_stratification/`, `b0_v2/`.
- **B0-v1** (fixed speed 10 m/s): 30 candidate logs → 28 valid (2 velocity artifacts excluded),
  speed axis **degenerate** (speed q33=q67=10.0) → 9 occupied classes of 27, entropy 3.067.
  Thresholds: length 53919.5/61805.2; width 3719.0/5414.1; speed 10.0/10.0.
- **B0-v2** (variable speed, Uniform 5–10 m/s, seeds 9001–9027, N=27): speed axis
  **non-degenerate** (q33=6.0697 < q67=7.8733); marginals 9/9/9 each axis; occupied 16/27;
  count sum = 27; remains E0. Thresholds: length 47037.0/56716.7; width 2840.1/3964.4.
- **B0-v2 N=90 review** (`b0_v2/n90_review/`): marginals 30/30/30; occupied 24/27; entropy 4.343.
  89/90 actual speed followed target; seed 9056 is a trace-sampling artifact (50% zero-delta samples).

## 5. Black evidence runs
| run | opponent | scenario/seeds | N | clean | breakthrough | defeat | source |
|---|---|---|---|---|---|---|---|
| formal_eval | B0 | S1/S2/S3 1001–1030 | 90 | 0.944 | 0.056 | 0.011 | `formal_eval_20260825/` |
| opponent_formal_eval | B3 | S1/S2/S3 1001–1030 | 90 | 0.822 | 0.156 | 0.056 | `opponent_formal_eval/` |
| phase0 corpus | B3 | S2 6001–6100 | 100 | 0.65 | 0.35 | 0.00 | `auto_harness/phase0/corpus/` |
| common_calibration | B0/B1/B2/B3 | S2 7001–7010 | 40 | see 02 | see 02 | see 02 | `policy_system/calibration/` |
| b0_v2 pilot/full | B0-v2 | S2 9001–9009 / 9001–9090 | 9 / 90 | 1.0 / 0.989 | 0.0 / 0.011 | 0 / 0 | `b0_v2/` |
| auto_0001 | AUTO1 | S2 7001–7010 + fresh + S1/S3 | 10+10+10 | 0.8/0.7/0.7 | 0.2/0.3/0.1 | 0.1/0.2/0.2 | `policy_system/evolution/auto_0001/` |

## 6. Open
- E1 (B1/B2) behavioral redundancy: B1-vs-B2 INCONCLUSIVE (behavior distance 0.371).
- AUTO1 response trigger fired 0/10 in calibration (all switches via bounded timeout fallback);
  `black-auto-0001-v2` would be required to change it.
