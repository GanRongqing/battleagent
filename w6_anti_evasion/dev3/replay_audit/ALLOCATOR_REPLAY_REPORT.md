# Allocator Decision Replay Report

## Dataset
- Sourced live runs: W6-dev3 FULL (F) S2 × B3 × seeds 4001–4003 (decision-neutral logger).
- Decision states collected: **2035** (`allocator_states.jsonl`, ~575–738 per episode).
- All states legal-belief only (no hidden truth stored by construction).

## Offline same-state replay
Recomputed allocators A (W5) → B(+Pred) → C(+Risk) → D(+Pursuit) → E(+Handoff) →
F(+Reserve) on each state with the SAME inputs (deep copy), no simulator call
(`allocator_replay_results.csv`, 12,210 rows). Sequential per episode (cooldown preserved).

## Component activation (of 2035 states)
| component | active states | rate |
|---|---:|---:|
| Prediction (corridor drift present) | 1519 | 74.6% |
| Risk (risk_score>0) | 1511 | 74.2% |
| Reserve (imminent/critical present) | 895 | 44.0% |
| Pursuit (free USV pool exists) | 36 | 1.8% |
| Handoff (committed target + free alt) | 36 | 1.8% |

## Decision change (assignment signature diff vs previous variant)
| step | changed states | rate |
|---|---:|---:|
| Prediction (B−A) | 37 | 1.8% (replay-fidelity artifact: offline W5 recompute differs from recorded base_alloc on 37 states; NOT a prediction effect) |
| Risk (C−B) | 0 | 0.0% |
| Pursuit (D−C) | 0 | 0.0% |
| Handoff (E−D) | 0 | 0.0% |
| Reserve (F−E) | 0 | 0.0% |

Net: **no W6 component changed any assignment across 2035 decision states.**

## Why the decision path is inert
1. The frozen W5 allocator commits almost every USV (coverage floor + marginal concentration),
   so a **free USV pool exists in only 1.8% of states**. Handoff and risk-reinforcement both
   require free alternatives → eligibility ≈ 1.8%.
2. In the 74 states that do have committed+free candidates, handoff-gate breakdown is
   ALT_NOT_BETTER 25, INSUFFICIENT_BENEFIT 22 (rest blocked by cooldown inside the sequential
   replay / already-committed alternative). No accepted handoff changed a signature.
3. Score-margin is NOT the limiter: when a better free alternative exists, contribution is
   large (mean 11×, median 4.4× the baseline top1−top2 margin; 70% of contributions exceed the
   margin). The limiter is **eligibility (free pool)** and **hysteresis/cooldown**, not magnitude.

## Determinism
- Same-state determinism: 100 sampled states × 10 repeats of variant F → 0 mismatch
  ⇒ allocator function is deterministic given a saved legal state.
- Hidden-truth counterfactual: PASS (injecting mock hidden fields changes nothing).

## Primary decision-level finding
W6 components are **computed and numerically active** (prediction/risk/reserve) but are
**inert at the assignment layer**: the decision mechanisms (handoff, reinforcement) never
fire because the base allocator leaves no free pool and hysteresis/cooldown block the rare
candidates. Outcome differences observed earlier across W6 variants on S2 were therefore
NOT caused by allocator actions — they were run-level noise / execution differences, not
assignment policy.
