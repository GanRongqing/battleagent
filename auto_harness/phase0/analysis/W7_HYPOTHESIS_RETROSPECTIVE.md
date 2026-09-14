# W7 Hypothesis Retrospective (N=100 W5 corpus, S2xB3)
- Recon/late-detection (recon-a/b): first_detection mean 1855.6 (clean) vs 1855.7 (fail) ->
  NOT discriminative. SUPPORTED = NO.
- Kill-chain (kc-a): F8 requires per-target hit/frozen data not derivable from logs; not
  estimable at pilot miner. SUPPORTED = UNKNOWN (no evidence for, consistent with no benefit).
- Coverage-gap (recon-b1): capacity_hole proxy higher in failures (32.7 vs 26.1) — weakly
  consistent with a capacity theme but coverage-gap UAV change itself was DROP. SUPPORTED = PARTIAL.
- Capacity-hole (gap-a): visible-not-engaged steps higher in failures; but gap-a live policy was
  worse. SUPPORTED = PARTIAL (symptom real, naive fix ineffective).
- Timing (fastpath): no timing discriminator captured. SUPPORTED = NO evidence.
Overall: W7's failures were consistent with optimizing non-discriminative proxies (e.g.,
detection timing) or using interventions whose downstream symptom was real but whose mechanism
failed; the single shared W5 failure signal is track-continuity/reacquire pressure.
