# 07 — Reproducibility Runbook

Python: `/root/miniconda3/envs/hsystem_env/bin/python`  |  Project: `/root/autodl-tmp/hsystem`

## 1. Start simulator + API
```bash
bash /tmp/opencode/start_services.sh          # base_server (3 sim_servers) + pomdp_api :8000
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/health   # expect 200
```
Per-episode config is written to `/tmp/opencode/rw_cfg.txt` by the runners.

## 2. Frozen hashes (verify before trusting results)
- White W5: `agent_hybrid_v5.py` sha256 `e823e7bed219f4693aa778a838df1400c161f8e7e44001502e5bceb0ae804252`
- Black artifacts/bundles: see `data/master_artifact_registry.csv`.
- Scenario builder: `hsystem/sim_script/20250819TZB/scenario_builder.py`.

## 3. Main runners
| runner | purpose | example |
|---|---|---|
| `run_opponent_formal.py` | W5 vs B0/B3 formal | `--scenario S2 --profiles B0_RANDOM B3_ADAPTIVE --seeds 1001..1030` |
| `common_policy_calibration.py` | B0–B3 S2 common calibration (7001–7010) | `python common_policy_calibration.py` |
| `auto_opponent_calibration.py` | AUTO1 candidate (S2/fresh/cross) | `--profile AUTO_FEINT_SWITCH --scenario S2 --seeds 7001..7010 --out-dir …` |
| `run_white_phase1.py` | W5 vs anti-leak candidate paired | `--agent agent_hybrid_w8_containment.py --tag cand --scenario S2 --seeds 8001..8030 --out-dir …` |
| `run_b0_v2.py` | B0-v2 variable-speed collection | `--seeds 9001..9090 --out-dir b0_v2/full` |
| `run_replay_set.py` | two-sided replay bundle | `--profile B0_RANDOM --scenario S2 --seeds 7001..7010 --out-dir /root/reports/replay_set_b0_s2` |

All runners are resumable by seed (existing rows in `EPISODES.csv` are skipped); they exclude
`wall<20s & UNFINISHED` infra failures and rerun those seeds.

## 4. Seed sets (do not mix)
| purpose | seeds | notes |
|---|---|---|
| formal (W5 vs B0/B3) | 1001–1030 | historical |
| Phase0 discovery | 6001–6100 | read-only after completion |
| common calibration | 7001–7010 | fp-v2 evidence |
| AUTO1 fresh | 7101–7110 | E3 validation |
| AUTO1 cross-scenario | 7201–7205 | S1/S3 |
| White Phase1 DEV | 8001–8030 | anti-leak paired (paused) |
| White Phase1 fresh | 8101–8130 | NOT STARTED |
| cross-opponent | 8201–8210 | NOT STARTED |
| B0-v2 | 9001–9090 | variable-speed baseline |
| holdout | 5001–5010 | **untouched** |

## 5. Analysis
- 27-class: `python b0_log_stratification/b0_stratify.py`; `python b0_v2/b0v2_stratify.py <dir>`
- B0-v1 vs v2: `python b0_v2/compare_v1_v2.py`
- Auto harness miner v2: `python auto_harness/phase1/failure_miner_v2.py`
- Replay: `python auto_harness/phase1/anti_leak_replay.py`
- DEV paired: `python auto_harness/phase1/analyze_phase1.py`
- Two-sided replay verify: `python verify_replay_set.py /root/reports/replay_set_b0_s2`
- Policy masters: `python docs/team_sync/build_master_tables.py`

## 6. Tests (all currently PASS)
`test_opponent_profiles.py` 154/154 · `test_policy_system.py` 10/10 · `test_strategy_library.py` 21/21
· `test_policy_fp2.py` 18/18 · `test_b0_27class.py` 11/11 · `test_b0_v2.py` 11/11 · `test_anti_leak.py` 12/12

## 7. Constraints
- Single simulator instance: run experiments **serially** (no concurrent runners).
- No physics/controller/BT/opponent-logic changes during evaluation.
- 5001–5010 untouched; 6001–6100 read-only.
