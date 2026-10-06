# 00 — PLAN: WAVE2 N=5 Confirmation + Contrastive Bottleneck Diagnosis

## Part 1 — WAVE2 N=5
- 6 WAVE2 strategies × 5 seeds (43001,43002 old + 43003,43004,43005 new) = 30 episodes.
- ACE frozen (sha256 7527253c…), deterministic step mode ON.
Gate: 18/18 new valid + 12 old valid = 30/30.
Outcomes → 03_WAVE2_N5_EPISODES.csv (30 rows), 04_WAVE2_N5_SUMMARY.csv (6 rows).

## Part 2 — Contrastive funnel diagnosis (no policy change)
Combat funnel conversion per strategy/episode/target:
DETECTED → PERSISTENT_TRACK → ACTIONABLE → ASSIGNED → ENTER_LOCK_RANGE → LEGAL_LOCK →
ACTIVE_LOCK → FIRST_HIT → KILL.
Report **conditional conversions**, not raw counts.

Constraint: pre-outcome / transition metrics preferred (avoid "detected-but-not-killed" conditioning).
If a field cannot be recovered reliably from existing logs ⇒ mark NOT_MEASURED (no fabricated proxies).
Only side-effect-free offline analysis scripts; any instrumentation must be logging-only and pass a
same-seed state-hash check before use (default: no instrumentation).

## Classification (descriptive, after N=5)
- ROBUST_WIN: pooled CER > 1 AND Exchange Wins ≥ 3/5
- ROBUST_LOSS: pooled CER < 1 AND Exchange Wins ≤ 2/5
- else BORDERLINE
(not a statistical-significance claim)

## Primary bottleneck taxonomy
TRACK_PERSISTENCE / KILL_CLOSURE / SURVIVAL_GEOMETRY / ALLOCATOR_REOPENED / MIXED /
INSUFFICIENT_EVIDENCE  — chosen ONLY from transition-level evidence.

## STOP
After 18 new episodes + N=5 summary + contrastive funnel + primary bottleneck:
STOP. No C5, no ACE change, no N10, no heuristic search.
