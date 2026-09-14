# Fastpath Profile Baseline (frozen W5, S2xB3)
Agent makes ~1 decision per 30-s sim macro (est decisions ~ sim/30, 500-1100/episode) and
completes each cycle in ~0.4-0.9 s wall (episode wall 380-470 s). Engine advances on an
apply/release macro cadence (MACRO_STEP ~30 s sim). Continuous-engine R1/R3 timing is
cadence-level, not agent-CPU-level.
Conclusion: policy-equivalent micro-optimization has negligible expected latency benefit.
FASTPATH = DROP (profile rationale; no sim spent).
