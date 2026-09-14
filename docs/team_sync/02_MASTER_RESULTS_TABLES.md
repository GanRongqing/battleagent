# 02 — Master Results Tables

All rows are extracted from repo artifacts by `docs/team_sync/build_master_tables.py`.
Machine-readable copies: `data/master_experiment_registry.csv`, `data/master_white_results.csv`,
`data/master_black_results.csv`, `data/master_artifact_registry.csv`, `data/master_policy_table.csv`,
`data/master_open_experiments.csv`.

> Missing values are `NOT_FOUND`. `defeat_rate` is computed from `result` containing `Defeat`.

## Experiment Registry (consolidated)

| experiment_id | category | scenario | white_policy | black_policy | seed_start | seed_end | valid_n | status | clean_rate | breakthrough_rate | defeat_rate | loss_mean | resolution_mean | result_file |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| formal_eval_20260825 | white_vs_black | S1/S2/S3 | W5 | B0(black-b0-v1) | 1001 | 1030 | 90 | HISTORICAL | 0.944 | 0.056 | 0.011 | 4.17 | 13733.0 | formal_eval_20260825/episode_results.csv |
| opponent_formal_eval[B0_RANDOM] | white_vs_black | S1/S2/S3 | W5 | B0_RANDOM | 1001 | 1030 | 90 | HISTORICAL | 0.944 | 0.056 | 0.011 | 4.17 | 13733.0 | opponent_formal_eval/episode_results.csv |
| opponent_formal_eval[B3_ADAPTIVE] | white_vs_black | S1/S2/S3 | W5 | B3_ADAPTIVE | 1001 | 1030 | 90 | HISTORICAL | 0.822 | 0.156 | 0.056 | 3.72 | 22438.0 | opponent_formal_eval/episode_results.csv |
| auto_harness_phase0 | white_vs_black | S2 | W5 | B3_ADAPTIVE | 6001 | 6100 | 100 | COMPLETE | 0.65 | 0.35 | 0.0 | 3.55 | 25920.0 | auto_harness/phase0/corpus/AUTO_HARNESS_EPISODES.csv |
| white_phase1_dev_w5 | white_candidate | S2 | W5 | B3_ADAPTIVE | 8001 | 8030 | 30 | COMPLETE | 0.5 | 0.467 | 0.133 | 3.2 | 27736.0 | auto_harness/phase1/dev_w5/EPISODES.csv |
| white_phase1_dev_cand | white_candidate | S2 | white-auto-0001-v1 | B3_ADAPTIVE | 8001 | 8018 | 18 | PAUSED | 0.722 | 0.278 | 0.167 | 3.06 | 25420.0 | auto_harness/phase1/dev_cand/EPISODES.csv |
| common_calibration[B0_RANDOM] | white_vs_black | S2 | W5 | B0_RANDOM | 7001 | 7010 | 10 | COMPLETE | 0.9 | 0.1 | 0.0 | 5.2 | 15799.0 | policy_system/calibration/COMMON_CALIBRATION_EPISODES.csv |
| common_calibration[B1_MULTI_AXIS] | white_vs_black | S2 | W5 | B1_MULTI_AXIS | 7001 | 7010 | 10 | COMPLETE | 0.0 | 0.9 | 1.0 | 1.3 | 29450.0 | policy_system/calibration/COMMON_CALIBRATION_EPISODES.csv |
| common_calibration[B2_COORDINATED_PRESSURE] | white_vs_black | S2 | W5 | B2_COORDINATED_PRESSURE | 7001 | 7010 | 10 | COMPLETE | 0.0 | 0.7 | 1.0 | 1.4 | 26145.0 | policy_system/calibration/COMMON_CALIBRATION_EPISODES.csv |
| common_calibration[B3_ADAPTIVE] | white_vs_black | S2 | W5 | B3_ADAPTIVE | 7001 | 7010 | 10 | COMPLETE | 0.6 | 0.4 | 0.1 | 2.5 | 28711.0 | policy_system/calibration/COMMON_CALIBRATION_EPISODES.csv |
| b0_v2_pilot | white_vs_black | S2 | W5 | black-b0-v2 | 9001 | 9009 | 9 | COMPLETE | 1.0 | 0.0 | 0.0 | 4.56 | 13319.0 | b0_v2/pilot/EPISODES.csv |
| b0_v2_full | white_vs_black | S2 | W5 | black-b0-v2 | 9001 | 9090 | 90 | COMPLETE | 0.989 | 0.011 | 0.0 | 3.58 | 12837.0 | b0_v2/full/EPISODES.csv |
| auto_0001_s2 | white_vs_black | S2 | W5 | black-auto-0001-v1 | 7001 | 7010 | 10 | COMPLETE | 0.8 | 0.2 | 0.1 | 3.4 | 29395.0 | policy_system/evolution/auto_0001/calibration_s2/EPISODES.csv |
| auto_0001_fresh | white_vs_black | S2 | W5 | black-auto-0001-v1 | 7101 | 7110 | 10 | COMPLETE | 0.7 | 0.3 | 0.2 | 3.8 | 28503.0 | policy_system/evolution/auto_0001/fresh_candidate/EPISODES.csv |
| auto_0001_cross_s1 | white_vs_black | S1 | W5 | black-auto-0001-v1 | 7201 | 7205 | 5 | COMPLETE | 0.6 | 0.2 | 0.2 | 1.8 | 30026.0 | policy_system/evolution/auto_0001/cross_S1_candidate/EPISODES.csv |
| auto_0001_cross_s3 | white_vs_black | S3 | W5 | black-auto-0001-v1 | 7201 | 7205 | 5 | COMPLETE | 0.8 | 0.0 | 0.2 | 6.6 | 28702.0 | policy_system/evolution/auto_0001/cross_S3_candidate/EPISODES.csv |
| w7_performance_push | secondary | S1/S2/S3 | W5-variants | B3? | NOT_FOUND | NOT_FOUND | 31 | HISTORICAL | 0.645 | 0.355 | 0.097 | 3.42 | 25537.0 | w7_performance_push/W7_DEV_RESULTS.csv |
| coevolution_final | secondary | S1/S2/S3 | W5/W6 | B0/B3 | NOT_FOUND | NOT_FOUND | 90 | HISTORICAL | 0.633 | 0.211 | 0.289 | 5.33 | 20667.0 | coevolution_final/final_episode_results.csv |
| bt_regression_eval | secondary | S1/S2/S3 | W5/BT | ? | NOT_FOUND | NOT_FOUND | 0 | HISTORICAL | NOT_FOUND | NOT_FOUND | NOT_FOUND | NOT_FOUND | NOT_FOUND | bt_regression_eval/integrated_results.csv |

## Notes / provenance

- `auto_harness_phase0`: Phase0 corpus CSV has no `friendly_usv_dead`; loss uses `friendly_usv_loss`.
- `white_phase1_dev_cand`: PAUSED; valid_n reflects the current partial run.
- `common_calibration[B1_MULTI_AXIS]` / `[B2_COORDINATED_PRESSURE]`: W5 was defeated in all 10
  S2×7001–7010 episodes (see 04). This is a real result, not a parsing error.
- `w7_performance_push`, `coevolution_final`, `bt_regression_eval`: secondary historical experiments;
  see their own directories for reports. `bt_regression_eval` summary file used here yielded 0 rows
  (`NOT_FOUND`); its real results live in `bt_regression_eval/*.csv`.

## SOURCE CONFLICT

- black-b0-v1 vs black-b3-v1 appears twice in `policy_validations` with distances **1.2316** (fp-v1, 93 ep)
  and **1.335** (fp-v2, 10 ep). Both are recorded; they are different fingerprint versions, not a bug.

## Data gaps (NOT FOUND / NOT RECORDED)

- White USV positions in pre-replay logs: NOT RECORDED (only counts + enemy TOP positions).
  Fixed only for the two-sided replay set `/root/reports/replay_set_b0_s2` (10 episodes).
- requested_n for most historical experiments: NOT_FOUND in the CSVs (only valid_n is recorded).
## Master Match Win-Rate Table (all completed matchups)

Source: `data/master_match_winrate.csv` (extracted from the CSVs in `result_file`).

| experiment | white | black | scenario | seeds | N | white victory | white clean | black win (breakthrough) | white defeat |
|---|---|---|---|---|---|---|---|---|---|
| formal_eval_20260825 | W5 | B0(black-b0-v1) | S1/S2/S3 | 1001–1030 | 90 | 0.989 | 0.944 | 0.056 | 0.011 |
| opponent_formal_eval[B0_RANDOM] | W5 | B0_RANDOM | S1/S2/S3 | 1001–1030 | 90 | 0.989 | 0.944 | 0.056 | 0.011 |
| opponent_formal_eval[B3_ADAPTIVE] | W5 | B3_ADAPTIVE | S1/S2/S3 | 1001–1030 | 90 | 0.944 | 0.822 | 0.156 | 0.056 |
| auto_harness_phase0 | W5 | B3_ADAPTIVE | S2 | 6001–6100 | 100 | 0.91 | 0.65 | 0.35 | 0.09 |
| white_phase1_dev_w5 | W5 | B3_ADAPTIVE | S2 | 8001–8030 | 30 | 0.867 | 0.5 | 0.467 | 0.133 |
| white_phase1_dev_cand | white-auto-0001-v1 | B3_ADAPTIVE | S2 | 8001–8018 | 18 | 0.833 | 0.722 | 0.278 | 0.167 |
| common_calibration[B0_RANDOM] | W5 | B0_RANDOM | S2 | 7001–7010 | 10 | 1.0 | 0.9 | 0.1 | 0.0 |
| common_calibration[B1_MULTI_AXIS] | W5 | B1_MULTI_AXIS | S2 | 7001–7010 | 10 | 0.0 | 0.0 | 0.9 | 1.0 |
| common_calibration[B2_COORDINATED_PRESSURE] | W5 | B2_COORDINATED_PRESSURE | S2 | 7001–7010 | 10 | 0.0 | 0.0 | 0.7 | 1.0 |
| common_calibration[B3_ADAPTIVE] | W5 | B3_ADAPTIVE | S2 | 7001–7010 | 10 | 0.9 | 0.6 | 0.4 | 0.1 |
| b0_v2_pilot | W5 | black-b0-v2 | S2 | 9001–9009 | 9 | 1.0 | 1.0 | 0.0 | 0.0 |
| b0_v2_full | W5 | black-b0-v2 | S2 | 9001–9090 | 90 | 1.0 | 0.989 | 0.011 | 0.0 |
| auto_0001_s2 | W5 | black-auto-0001-v1 | S2 | 7001–7010 | 10 | 0.9 | 0.8 | 0.2 | 0.1 |
| auto_0001_fresh | W5 | black-auto-0001-v1 | S2 | 7101–7110 | 10 | 0.8 | 0.7 | 0.3 | 0.2 |
| auto_0001_cross_s1 | W5 | black-auto-0001-v1 | S1 | 7201–7205 | 5 | 0.8 | 0.6 | 0.2 | 0.2 |
| auto_0001_cross_s3 | W5 | black-auto-0001-v1 | S3 | 7201–7205 | 5 | 0.8 | 0.8 | 0.0 | 0.2 |
| w7_performance_push | W5-variants | B3? | S1/S2/S3 | NOT_FOUND–NOT_FOUND | 31 | 0.903 | 0.645 | 0.355 | 0.097 |
| coevolution_final | W5/W6 | B0/B3 | S1/S2/S3 | NOT_FOUND–NOT_FOUND | 90 | 0.711 | 0.633 | 0.211 | 0.289 |
| bt_regression_eval | W5/BT | ? | S1/S2/S3 | NOT_FOUND–NOT_FOUND | 0 | NOT_FOUND | NOT_FOUND | NOT_FOUND | NOT_FOUND |

Notes:
- `auto_harness_phase0`/`coevolution_final` have no `result` column; victory/defeat derived from `outcome`.
- `bt_regression_eval` has no consolidated summary row (NOT_FOUND); use `bt_regression_eval/*.csv`.
- black win = breakthrough episode rate; White victory includes breakthrough-wins.