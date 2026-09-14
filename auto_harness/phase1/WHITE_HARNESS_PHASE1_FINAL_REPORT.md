# White Harness Phase 1 — Anti-Leak Containment (status)

## Baseline
- White = W5 (agent_hybrid_v5.py), FROZEN (unmodified; hash unchanged).
- Phase 0: S2 x B3, N=100 -> clean 65 / breakthrough-win 26 / defeat 9;
  all 35 non-clean have exactly one breakthrough.

## Root-cause update (evidence)
- Detection/first-lock/first-kill NOT discriminative.
- Miner v2: raw lost-track / capacity-hole / reacquire counts are higher in failures
  only because failures last ~2x longer; per-1000-step and per-1000-sim-s rates are
  LOWER in failures. => track continuity is NOT the primary cause (duration artifact).
- New taxonomy: F-LEAK = 26 (all enemies eventually killed; containment/timing loss),
  F-ATTRITION = 9 (survivors / high loss).

## Candidate
- policy_id = white-auto-0001-v1, family = anti_leak_containment, parent = W5.
- entrypoint = agent_hybrid_w8_containment.py; bundle hash =
  f44f445c40e7acbdbda9799dfd4d00a3005786780ce6309aa71c10b1731f0a26.
- Allocator-only overlay (WHO), execution HOW untouched.

## Mechanism verification (offline)
- Unit/fair-play tests: 12/12 PASS (WC-T1..T10 + W5-equivalence + source audit).
- W5-equivalence outside trigger: 500/500 synthetic states identical.
- Offline proxy replay (6001-6100, no per-step USV positions): failure trigger
  coverage HIGH-proxy 1.0, CRITICAL-proxy 0.343; clean false-trigger HIGH-proxy 0.431,
  CRITICAL-proxy 0.077. Mechanism fires; not an outcome claim.

## DEV tournament (seeds 8001-8030, S2 x B3, paired W5 vs candidate)
- IN PROGRESS (resumable runner run_white_phase1.py). N=30 each target.
- Results/analysis will be written to ANTI_LEAK_DEV_RESULTS.csv / ANTI_LEAK_DEV_REPORT.md
  by auto_harness/phase1/analyze_phase1.py once episodes complete.

## Fresh / cross-opponent
- Not started (gated on a promising DEV result, per stop gate).

## Guardrails
- 5001-5010 untouched; 6001-6100 read-only (offline replay only); no physics change.
