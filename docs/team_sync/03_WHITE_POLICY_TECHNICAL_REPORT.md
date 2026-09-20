# 03 — White Policy Technical Report

## 1. W5 — frozen deterministic baseline
- File: `agent_hybrid_v5.py`; sha256 `e823e7bed219f4693aa778a838df1400c161f8e7e44001502e5bceb0ae804252`.
- Architecture: TrackManager(belief) → ThreatAllocator (WHO/WHAT/TARGET) → USVController/UAVManager (HOW)
  → ActionSafety. Deterministic; LLM commander disabled (`LLM_ENABLED=false`) in all reported runs.
- Results (extracted):
  | experiment | opponent | N | clean | breakthrough | defeat | loss | resolution | source |
  |---|---|---|---|---|---|---|---|---|
  | formal_eval_20260825 (S1/S2/S3, 1001–1030) | B0 | 90 | 0.944 | 0.056 | 0.011 | 4.17 | 13733 | `formal_eval_20260825/episode_results.csv` |
  | opponent_formal_eval (S1/S2/S3, 1001–1030) | B3 | 90 | 0.822 | 0.156 | 0.056 | 3.72 | 22438 | `opponent_formal_eval/episode_results.csv` |
  | auto_harness_phase0 (S2, 6001–6100) | B3 | 100 | 0.65 | 0.35 | 0.00 | 3.55 | 25920 | `auto_harness/phase0/corpus/AUTO_HARNESS_EPISODES.csv` |
  | common_calibration (S2, 7001–7010) | B0 | 10 | 0.90 | 0.10 | 0.00 | 5.2 | 15799 | `policy_system/calibration/COMMON_CALIBRATION_EPISODES.csv` |
  | common_calibration (S2, 7001–7010) | B1 | 10 | 0.00 | 0.90 | 1.00 | 1.3 | 29450 | 同上 |
  | common_calibration (S2, 7001–7010) | B2 | 10 | 0.00 | 0.70 | 1.00 | 1.4 | 26145 | 同上 |
  | common_calibration (S2, 7001–7010) | B3 | 10 | 0.60 | 0.40 | 0.10 | 2.5 | 28711 | 同上 |
- Note: W5 is much weaker vs B1/B2 (defeat 10/10 on S2×7001–7010) than vs B0/B3.

## 2. W6 — completed adaptive generation (not a win-rate upgrade)
Source: `W6_FINAL_REPORT.md`. Key architecture lesson reused this round:
- allocator/execution decoupling; **execution override = 0**; legacy W5 controller reused.
- fair-play + hidden-truth + same-state determinism PASS; commitment-state abstraction; 2035-state replay dataset.
- Negative: dev2 predictive-waypoint execution override caused attrition collapse; FREE reinforcement
  falsified; SOFT rebalancing did not generalize; **no stable clean-win improvement over W5**.

## 3. W7 — completed performance push (no robust improvement)
Source: `W7_FINAL_REPORT.md`.
- W5 baseline on its DEV (S2×B3, 4001–4010): clean 8/10 (0.80), breakthrough 2, loss 2.7.
- Five attack surfaces (Recon-A, KC-A, Recon-B1, Fastpath, Gap-A) all DROP; early signals reversed at
  larger N. 5001–5010 not used.

## 4. white-auto-0001-v1 — anti-leak containment candidate
- Family `anti_leak_containment`; parent `white-w5-baseline`; status `candidate`.
- Entry: `agent_hybrid_w8_containment.py`; artifact hash `5fe78b73ae07…`; bundle `2fcde232ba81…`.
- Change surface: **ThreatAllocator overlay only** (WHO/WHAT/TARGET); controller/BT/physics unchanged.
- Mechanisms: M1 crossing-risk estimator (legal ETA to BREAK_X), M2 effective blocker checker,
  M3 minimal containment assignment (one blocker, TTL 900 s, release on kill/expiry/no-position).
- Verification (repo-backed):
  | check | result | source |
  |---|---|---|
  | unit / fair-play / hidden-truth / variable cardinality | 12/12 PASS | `test_anti_leak.py` |
  | W5 equivalence outside trigger | 500/500 identical | `test_anti_leak.py` |
  | offline replay failure coverage (HIGH proxy) | 1.0 | `auto_harness/phase1/ANTI_LEAK_REPLAY.json` |
  | offline replay critical coverage | 0.343 | 同上 |
  | clean false-trigger (HIGH / CRITICAL) | 0.431 / 0.077 | 同上 |
- DEV paired (S2×B3, 8001–8030) — **IN PROGRESS / PAUSED**:
  | arm | N | clean | breakthrough | defeat | loss | resolution | source |
  |---|---|---|---|---|---|---|---|
  | W5 | 30 | 0.500 | 0.467 | 0.133 | 3.2 | 27736 | `auto_harness/phase1/dev_w5/EPISODES.csv` |
  | candidate | 18 (paused) | 0.722 | 0.278 | 0.167 | 3.06 | 25420 | `auto_harness/phase1/dev_cand/EPISODES.csv` |
- Verdict: mechanism VALIDATED; performance **NOT YET VALIDATED** (N=18 < 30, paired analysis pending).

---
## GATE UPDATE — anti-leak DEV paired (8001–8030, N=30)
| metric | W5 | candidate |
|---|---|---|
| clean | 0.500 | 0.733 |
| breakthrough | 0.467 | 0.200 |
| defeat | 0.133 | 0.200 |
| loss (mean/median) | 3.20 / 3 | 3.37 / 3 |
| resolution | 27736 | 26594 |
Paired: breakthrough 11:3 (p=0.057), defeat 3:5 (p=0.727). Mechanism triggers 19 across 11/30 episodes.
Verdict **SUPPORTED (provisional)**. Source: `auto_harness/phase1/WHITE_PHASE1_FINAL_REPORT.md`.

---
## GATE UPDATE — anti-leak FRESH (8101–8130, N=30) = FAIL
DEV breakthrough 0.467→0.200 did not reproduce: FRESH W5 0.233 → candidate 0.367 (reversed).
Clean 0.733→0.633 (reversed). Mechanism fired less (6/30 vs 11/30 episodes).
Decision: white-auto-0001-v1 NOT promoted; W5 remains frozen current. Source: `auto_harness/phase1/ANTI_LEAK_FRESH_REPORT.md`.
