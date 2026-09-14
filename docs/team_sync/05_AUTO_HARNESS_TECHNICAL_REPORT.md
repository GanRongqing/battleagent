# 05 — Auto Harness Technical Report

## 1. Phase 0 discovery corpus
- Setup: frozen W5 × B3_ADAPTIVE, S2 (10 USV + 10 UAV vs 20 Black USV), seeds 6001–6100, N=100.
- Source: `auto_harness/phase0/corpus/AUTO_HARNESS_EPISODES.csv` (+ `AUTO_HARNESS_FAILURE_EVENTS.jsonl`).
- Outcome: **clean 65 / breakthrough-win 26 / defeat 9**; abnormal 0.
- **35/35 non-clean episodes have exactly one breakthrough event** (every failure has
  `black_breakthrough=1`).
- fp: no Black geometry sidecar in this corpus (only White logs).

## 2. Root-cause correction (W5_LOSS_ANALYSIS.md + Failure Miner v2)
- Detection / kill-chain onset NOT discriminative:
  first_detection 1855.6 (clean) vs 1855.7 (fail); first_lock 7420 vs 7407; first_kill 8333 vs 8343.
- Raw lost-track / capacity-hole / reacquire counts are higher in failures, but failures last ~2×;
  duration-normalized rates (per 1000 steps / per 1000 sim-s) are **LOWER** in failures.
  → track continuity / reacquire is **NOT** the primary cause.
- Real signature: single leak + long resolution tail + forward containment gap:
  resolution 19963 (clean) vs 36983 (fail); resolution>30000: 0% vs 88.6%;
  post-last-kill tail 3780 s vs 14768 s.

## 3. Failure taxonomy (miner v2)
Source: `auto_harness/phase1/failure_miner_v2.py`, `FAILURE_MINER_V2_REPORT.md`.
- **F-LEAK = 26** (breakthrough, all enemies eventually killed).
- **F-ATTRITION = 9** (breakthrough + enemy survivors / high loss).
- LOST_TRACK / REACQUIRE_FAILURE / CAPACITY_HOLE are retained as **secondary mechanism features**.
- Miner v2 stores raw_count, rate_per_1000_steps, rate_per_1000_sim_seconds, absolute-time bins.

## 4. Phase 1 — anti-leak containment
- Candidate `white-auto-0001-v1` (see 03). Allocator overlay only; execution_override=false.
- Offline mechanism replay (proxy on 6001–6100, read-only):
  failure coverage (HIGH proxy) 1.0; CRITICAL 0.343; clean false-trigger HIGH 0.431 / CRITICAL 0.077;
  median actionable lead 20793 s. Source: `auto_harness/phase1/ANTI_LEAK_REPLAY.json`.
  NOTE: proxy only (no per-step White USV positions in the corpus); mechanism sanity, not outcome.
- DEV paired (S2×B3, 8001–8030): W5 30/30 done; candidate **PAUSED at 18/30**.
  Current partial: W5 clean 0.500 / breakthrough 0.467; candidate clean 0.722 / breakthrough 0.278.
  Source: `auto_harness/phase1/dev_w5/EPISODES.csv`, `dev_cand/EPISODES.csv`.
- Fresh validation (8101–8130) and cross-opponent (8201–8210): **NOT STARTED**.

## 5. Causal-verdict vocabulary (used by analyze_phase1.py)
MECHANISM_NOT_FIRING / HYPOTHESIS_NOT_SUPPORTED / BAD_TRADEOFF / SUPPORTED.
Current status: mechanism validated; performance verdict **PENDING** (DEV incomplete).

## 6. Two-sided replay instrumentation (new)
- `run_replay_set.py` records BOTH sides per poll (white_usv/white_uav/black_visible/engaged).
- 10-episode set: `/root/reports/replay_set_b0_s2` (B0_RANDOM×W5, S2, 7001–7010), verified
  BOTH SIDES PRESENT for all 10.
