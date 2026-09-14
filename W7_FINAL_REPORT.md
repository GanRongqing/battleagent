# White Harness W7 — Final Performance Report

## 1. Objective
Maximize the White fair-play clean-win rate vs B3_ADAPTIVE (physics/opponent frozen, legal
observation only, no RL).

## 2. W5 baseline (S2 × B3, DEV 4001–4010)
clean 8/10 (0.80), breakthrough 2, friendly loss mean 2.7.

## 3–4. Candidate search (all on W5 base; execution override = 0)
- Recon-A (UAV screen_priority + high-risk reacquire preset): N=3 clean 2/3 -> DROP.
- KC-A (kill-chain completion follow-up overlay): N=5 clean 3/5 (0.60) vs W5 4/5 -> DROP.
- Recon-B1 (coverage-gap dynamic screen, UAV redirect): N=3 clean 1/3 -> DROP (collapse).
- Fastpath (policy-equivalent runtime): DROP by profile — agent cycle ~0.5 s vs ~30 s sim macro,
  latency is not the bottleneck.
- Gap-A (FREE-only pre-position into 0-capacity RISING holes): N=10 clean 6/10 (0.60) vs W5
  8/10, breakthrough 5 vs 2, loss 4.2 vs 2.7 -> DROP (initial 5/5 was seed luck; seeds 4007-4010
  collapsed).

## 5–7. Best candidate
None robustly beat W5. Every promising early signal reversed at larger N (classic small-N
sampling of a noisy continuous-time simulator).

## 8–10. S2 DEV10 / 3-scale / fresh holdout
Not justified: no candidate passed S2 DEV10 (Gap-A N10 was worse). 5001–5010 were NOT used.

## 11–14. Fair play / execution ownership / determinism / architecture
All candidates: legal observation only; USV HOW = W5 (execution override 0); no seed/profile
branches; variable cardinality; hidden-truth/determinism PASS. Resource-balance proxies showed
failed candidates did NOT over-concentrate vs W5.

## 15. W5 vs W6 vs W7
W5 remains the strongest deterministic performance baseline on S2×B3. W6 = completed adaptive
generation (dev3 deliverable, not a win-rate upgrade). W7 = completed performance-push
generation with NO ROBUST WIN-RATE IMPROVEMENT; W7-final is a generation record pointing to the
W5-equivalent runtime (no new policy performance claim).

## 16. Negative findings
Five independent attack surfaces failed to beat W5; consistent with W5 being at/near a local
optimum of the hand-crafted deterministic search space on this opponent/scale.

## 17. Final decision
W7 STATUS = COMPLETE (completed_no_robust_improvement). Best deterministic White harness = W5
(frozen). No fake improvement reported.
