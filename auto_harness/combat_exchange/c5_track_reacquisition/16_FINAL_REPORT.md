# 16 — FINAL REPORT: Stage A + C5 Track-Aware Reacquisition

Parent = ACE (sha256 7527253c…, UNCHANGED). Candidate = C5 (agent_hybrid_track_reacquire.py, white-combat-0006-v1).

## Stage A
- Instrumentation: none added (frozen logs lack per-target persistence fields; avoided truth-leak risk).
- Track hypothesis: **INSUFFICIENT** for direct per-target evidence; aggregate proxy points to
  DETECTION/SEARCH (peak visible tracks 16.4 vs 7.35), not stale-window persistence.
- Architectural finding: the frozen parent **already** retains stale ownership + drives a
  constant-velocity predicted-position standoff (agent_hybrid_v5.py:2048,2098) → C5's delta is small.

## Stage B (C5)
- Unit tests: **11/11 PASS** (incl. all-fresh exact no-op; predicted cannot lock/fire; expiry bounds).
- Determinism: candidate is a pure post-process on the parent's actions; no new RNG.
- Eval (W2-1/W2-2/W2-4/W2-6 × 5 seeds = 20 C5 episodes) launched; partial: W2-1 C5 = 2/20, 2/20, 1/20
  = identical to ACE.

## Verdict
**INCONCLUSIVE / NO_EFFECT on the hard case** (W2-1 unchanged). C5 is safe (unit-tested, bounded,
lock/fire legality untouched) but does not move the hard WAVE2 outcomes, because the bottleneck is
upstream detection/search, not stale-track ownership retention.

## Next
Bottleneck remains **TRACK (detection/search)** → then SURVIVAL_GEOMETRY. Do NOT implement C6 here.

## Notes
- No ACE modification, no allocator change, no survival/retreat logic, no kill-closure change, no LLM.
- Services were unstable during the eval (API restarts), so the 20-episode run is partial.
