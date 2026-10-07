# 00 — PLAN: Stage A (track instrumentation) + Stage B (C5 track-aware reacquisition)

Parent = ACE (agent_hybrid_allocator_expand.py, sha256 7527253c…, UNCHANGED).
Stage A: direct per-target track evidence (logging-only; invariance-gated).
Stage B: C5 = TRACK_AWARE_REACQUISITION (single mechanism), independent candidate file.
Eval: W2-1/W2-6 (hard) + W2-2/W2-4 (control) × seeds 43001–43005 × {ACE(frozen), C5} = 20 new C5 episodes.

## Key architectural finding (from reading the frozen W5/ACE controller)
`USVController.step` (agent_hybrid_v5.py:2002) **already**:
- retains ownership for a stale-but-present track (line 2048-2051: release only if the track is dropped/killed), and
- during non-visible stale windows it drives a tightening standoff to the **predicted_position** (line 2098-2099).
So ownership retention + constant-velocity predictive approach are ALREADY present in the frozen parent.
The observed WAVE2 loss signature is a **front-of-funnel detection/search deficit** (peak visible
tracks 7.35 vs 16.4), i.e. the White force sees fewer of the 30 enemies — which ownership retention
cannot fix. Stage A must therefore confirm whether the residual track gap is (a) detection/search or
(b) stale-window persistence; C5 addresses (b) only.
