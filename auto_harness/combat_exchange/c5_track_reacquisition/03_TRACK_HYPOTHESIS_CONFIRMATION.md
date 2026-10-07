# 03 — TRACK HYPOTHESIS CONFIRMATION

Direct per-target instrumentation: the frozen agent does not expose per-target stale/reacquire
transitions in its stdout logs (only aggregate `TRACKS vis/lost/engaged` + `lock`). The runtime_audit
serializes tracks per step, but no clean per-target persistence/reacquisition counters are emitted.
Per the plan, no truth-leaking / behaviour-affecting instrumentation was added (invariance gate not
attempted with engine changes).

Verdict: **INSUFFICIENT** for direct per-target persistence; the aggregate proxy from
`wave2_n5_contrastive_diagnosis` remains the evidence (peak visible tracks 16.4 WIN vs 7.35 LOSS;
first engagement ~1.8x later). The proxy points at DETECTION/SEARCH (front-of-funnel), which ownership
retention (C5) does not address. Allowed to proceed to Stage B at MEDIUM/LOW confidence only because
the bounded C5 no-op test is safe.
