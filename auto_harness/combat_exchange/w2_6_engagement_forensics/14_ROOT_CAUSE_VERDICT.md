# 14 — ROOT-CAUSE VERDICT (W2-6)

## Primary bottleneck
**LOW_CONCURRENT_LOCK_CAPACITY / LOCK_TEMPORAL_FRAGMENTATION.**
White's own-lock runs are near-ideal 300 s windows (top runs all = 300 s), but they **do not overlap**:
max concurrency 4 (ACE/C10) vs **9** on the winning W2-4. Kill throughput ≈ sustained-window count;
W2-6 ACE 16 windows vs W2-4 26. Fewer simultaneous 300 s windows ⇒ fewer completed hits ⇒ fewer kills.

## Secondary bottleneck
**PRELOCK_ATTRITION via the freeze→second-hit chain.**
8/18 (ACE) and 5/16 (C10) White USVs die **before ever locking**. The engine freezes a victim for 300 s
after its first hit (01_LOCK_ENGINE_SEMANTICS), so a struck unit cannot lock and is finished by the
second hit. This removes ~half the force from the lock pool, which is *why* concurrency stays low.

## Earliest failing stage vs W2-4
At the **first hostile lock → own-lock** stage: W2-4 loses only 1 unit before it locks; W2-6 loses 8.
The concurrency ceiling is a *consequence* of this early attrition, not an independent cause.

## What is legally actionable vs engine-only
- Actionable by White: **survival/timing** (avoid the first hit; keep units lock-capable) and
  **arrival overlap** (get more units into ≤40 km at the same time).
- Engine-only (offline): the exact freeze/300 s/hit semantics — NOT controllable by White.
- Correlation only (not proven causal): higher concurrency ⇔ better exchange; C10 raised windows 16→20
  (ratio +24%) without raising max concurrency 4, showing concurrency and total-window count are related
  but distinct levers.

## Confidence
MEDIUM. Source semantics HIGH (readable). Per-scenario numbers HIGH for seed 43001, but N≈1 (13).
