# Final Diagnosis — Allocator Decision Replay + Repeatability

| Question | Result | Evidence |
|---|---|---|
| Components active? | Partially | Prediction 74.6%, Risk 74.2%, Reserve 44.0% active as features; Pursuit/Handoff 1.8% (free pool). |
| Components change decisions? | NO | 0 / 2035 assignment changes for Risk/Pursuit/Handoff/Reserve (Prediction 37 is a W5-replay fidelity artifact). |
| Which component changes most? | none | all 0 on the assignment signature. |
| Score too weak vs baseline margin? | NO | mean contribution/margin ≈ 11×, median 4.4×; not the limiter. |
| Gates too restrictive? | PARTLY | free-USV pool absent in ~98% of states; hysteresis/cooldown block the rare 74 candidates. |
| Allocator deterministic same-state? | YES | 100 states × 10 repeats → 0 mismatch; hidden-truth PASS. |
| Same-seed live repeatable? | NO | W5 S2 seed4002 flips Victory↔Defeat; vt spread 11–15k s; coarse divergence mid-game (~idx 29–31). |
| Noise source category | R1/R3 (trajectory/timing-engine), NOT R2 policy | allocator deterministic given same state, live diverges. |

## Conclusion case

**CASE A + CASE C**:
- A — Components inert: features are computed and numerically active, but the allocator
  decision mechanisms never change an assignment on 2035 states, because (i) the frozen W5
  base allocator leaves almost no free USV pool (~1.8%), and (ii) hysteresis/cooldown block
  the rare candidates. Hence **the W6 allocator overlay is effectively a passthrough**; its
  earlier apparent outcome effects were not assignment policy.
- C — The allocator function is deterministic on a saved legal state, while the LIVE simulator
  is highly nondeterministic same-seed (outcome flips). Therefore episode outcome is not a
  stable small-sample signal for component attribution.

## Recommended next step (NOT run this round)
Redesign the decision integration so components can express themselves under the frozen
execution layer, e.g. by freeing a bounded reserve explicitly, OR switch allocator-level
questions to same-state replay + larger paired outcome samples. Stop live N≈3 outcome
comparisons for component debugging.
