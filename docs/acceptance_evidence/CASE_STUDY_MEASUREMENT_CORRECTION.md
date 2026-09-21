# Case Study: Measurement Correction (proxy refutation)

- Phase3 claimed AE-F5 "ASSIGNED_ON_LOST_TRACK" (disp 12/15, two 8/10) and a large
  ASSIGNED->ENGAGED gap, using step-level `[ASSIGN]` proxy logs.
- Phase4 (instrumented W5, `agent_hybrid_w5_tracklog.py`) showed the allocator only creates
  new assignments for fresh/visible tracks (vis 0.83-1.0, age ~0, conf=1.0) — premise REFUTED.
- Phase5 (instrumented `agent_hybrid_w5_translog.py`, seeds 9601-9603): canonical
  alloc->lock 0.812 (disp) / 0.783 (two); NO_LOCK 8/39 = 0.205 -> NO_ACTIONABLE_ROOT_CAUSE.
- Lesson: step-level proxy logs MUST NOT override runtime instrumentation. Always confirm
  causal claims with canonical instrumentation before building a candidate.
