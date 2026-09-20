# 00 — Team Sync Index

## 当前项目一句话
Frozen deterministic White baseline (W5) + Black policy taxonomy (E0–E3) +
Policy/Fingerprint registry + failure-driven Auto Harness evolution pipeline.

## Current Snapshot
| 项 | 值 | 来源 |
|---|---|---|
| Best deterministic White | W5 (`agent_hybrid_v5.py`, sha256 `e823e7bed219f469…`) | `agent_hybrid_v5.py` |
| Current White candidate | `white-auto-0001-v1` (anti_leak_containment), status `candidate`, parent `white-w5-baseline` | strategy_library.db |
| Registered Black policies | black-b0-v1 (sealed), black-b0-v2 (validation), black-b1-v1/b2-v1/b3-v1 (active), black-auto-0001-v1 (active) | strategy_library.db |
| Empirical Black classes | E0 Random (B0-v1/v2), E1 Structured Multi-Axis (B1/B2), E2 Adaptive Replanning (B3), E3 Phased Feint-Switch (AUTO1) | `policy_system/evolution/auto_0001/AUTO_POLICY_TAXONOMY.md` |
| Current main White failure mode | single boundary leak / containment failure (35/35 non-clean have exactly 1 breakthrough) | `auto_harness/phase0/analysis/AUTO_HARNESS_FAILURE_SUMMARY.md`, `auto_harness/phase1/FAILURE_MINER_V2_REPORT.md` |
| Current active experiment | White Phase1 anti-leak DEV paired (8001–8030) — **PAUSED** at candidate valid_n=18/30 | `auto_harness/phase1/dev_cand/EPISODES.csv` |
| Latest completed classification task | B0-v2 27-class stratification (official N=27; N=90 review) | `b0_v2/B0_V2_27CLASS_THRESHOLDS.json`, `b0_v2/n90_review/` |
| Current promotion gate | DEV paired → fresh (8101–8130) → cross-opponent (8201–8210) | this pack / `auto_harness/phase1/WHITE_HARNESS_PHASE1_FINAL_REPORT.md` |

## Documentation Map
- `00_TEAM_SYNC_INDEX.md` — entry point, snapshot, claim safety.
- `01_SYSTEM_ARCHITECTURE.md` — data flow (White/Black/observation/action/library/harness).
- `02_MASTER_RESULTS_TABLES.md` — consolidated experiment results + provenance.
- `03_WHITE_POLICY_TECHNICAL_REPORT.md` — W5/W6/W7 + anti-leak candidate.
- `04_BLACK_POLICY_AND_TAXONOMY_REPORT.md` — Black policies, E-classes, 27-class strata.
- `05_AUTO_HARNESS_TECHNICAL_REPORT.md` — Phase0 corpus, failure miner v2, Phase1.
- `06_STRATEGY_LIBRARY_AND_POLICY_SYSTEM.md` — DB schema/API/fingerprint/validation.
- `07_REPRODUCIBILITY_RUNBOOK.md` — exact commands, seeds, hashes.
- `08_OPEN_ISSUES_AND_NEXT_STEPS.md` — open items.
- `data/*.csv` — machine-readable masters.

## What is safe to claim today?
### VALIDATED (repo-backed)
- W5 is the frozen deterministic White baseline (sha256 above).
- Phase0 N=100 (W5×B3, S2, 6001–6100): clean 65, breakthrough-win 26, defeat 9; 35/35 non-clean have exactly 1 breakthrough.
- Failure root-cause correction: detection/first-lock/first-kill NOT discriminative; raw lost-track/reacquire/capacity differences are duration artifacts (miner v2).
- anti-leak candidate implementation + mechanism: unit/fair-play/W5-equivalence 12/12; replay failure coverage 1.0, CRITICAL clean false-trigger 0.077.
- B0-v2 speed axis non-degenerate (N=27: speed q33=6.0697 < q67=7.8733); remains E0.
- B0-v1 27-class pipeline (N=28 valid, speed degenerate).
- Black policy taxonomy E0–E3 and pairwise verdicts (see 04).
### IN PROGRESS
- anti-leak DEV paired performance (W5 30/30 done; candidate 18/30 paused).
### NOT YET VALIDATED
- anti-leak fresh validation (8101–8130) — NOT STARTED.
- anti-leak cross-opponent generalization (8201–8210) — NOT STARTED.
- candidate `active` status / promotion — NOT DONE.

> Provenance rule: every number in this pack is extracted from files listed per row. Where a
> value is absent it is marked `NOT_FOUND` / `NOT_RECORDED`; conflicts are marked `SOURCE CONFLICT`.

---
## GATE UPDATE — Phase1 DEV complete (S2×B3, 8001–8030, paired N=30)
- W5: clean 0.500 / breakthrough 0.467 / defeat 0.133 / loss 3.20 / res 27736
- candidate white-auto-0001-v1: clean 0.733 / breakthrough 0.200 / defeat 0.200 / loss 3.37 / res 26594
- paired breakthrough 11:3 (McNemar p=0.057); paired defeat 3:5 (p=0.727)
- **DEV verdict = SUPPORTED (provisional)**; promotion gated on fresh 8101–8130 (IN PROGRESS).

---
## GATE UPDATE — Phase1 FRESH complete (8101–8130, paired N=30)
- W5: clean 0.733 / breakthrough 0.233 / defeat 0.067
- candidate: clean 0.633 / breakthrough 0.367 / defeat 0.033
- **FRESH VERDICT = FAIL**: DEV breakthrough improvement did not reproduce (direction reversed).
- Decision: NO promotion; W5 remains frozen current; Phase2 stacking NOT entered.
