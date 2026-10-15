# 12 — FINAL VERDICT: C11 = DROP

## What C11 was
`SPARE_SUPPORT_ONLY` (parent C10): divert a support only if it is >40 km from any agent-visible track.

## Result
- **W2-6 C11 = 11/16 (0.688), trajectory hash `b177365238ca` — IDENTICAL to C10.**
- W2-4 C11 = 12/7 (1.714) = C10; W2-2 C11 = 4/19 = C10/ACE.
- C11 package FORM events are byte-identical to C10 → **the gate never fires**.

## Why it failed (cause analysis)
The Shadow measured "engaged support" using the **game-log `active_enemies`** (the simulator's radar
capture), which showed 8/14 supports within 40 km. But the **agent's legal observable is its TrackManager
tracks**; at those FORM times the diverted supports had **no agent-visible track within 40 km** → the gate
condition was already false → C11 ≡ C10. The discrepancy is itself the real signal: the enemy was
physically close but **not in the agent's track set** (observation gap), so no *agent-side* decision was
wrong to fix.

## Verdict: DROP
- Trigger = 0 (agent-legal) → per Gate A "no action difference → STOP".
- No mechanism change, no outcome change, no control change.
- H1 (task churn) also rejected in Shadow (W2-6 churn 17 < winning W2-4 churn 47).

## Honest conclusion for this round
No minimal *agent-side software* mechanism is supported by the evidence: the W2-6 limiter is
**geometric/observational** (concurrent in-range lock capacity; enemies often outside the agent's track
set), not an unnecessary control switch. Exchange ratio > 1.000 was **NOT** reached. Confidence MEDIUM.
