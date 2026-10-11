# 00 — PLAN: FINAL BOTTLENECK AUDIT (seed independence + zero-lock failure)
Frozen: ACE, C7, Black, TrackManager, ThreatAllocator, USVController, ActionSafety, legality, sensors,
weapons, routes. Allowed: static audit, offline log parsing, logging-only instrumentation, RNG seed
plumbing fix, minimal determinism regression.
Stages: A seed plumbing audit → B seed repair → C zero-lock funnel (W2-1 vs W2-4) → D minimal replay →
E evaluation independence audit → F root-cause verdict.
