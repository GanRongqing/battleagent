# W6-dev3 Isolation — Primary Suspect Report

## Question

Which incremental allocator component first introduces a significant negative contribution?

## Method

Strict cumulative gates B→F (prediction, +risk, +pursuit-cost, +handoff, +reserve) on
S2 × B3 × 4001–4003, legacy execution, uniform UAV behaviour. N=3.

## Answer (honest)

**NO SINGLE COMPONENT ISOLATED AS THE PRIMARY NEGATIVE CONTRIBUTOR.**

Reasons (see `ALLOCATOR_ISOLATION_REPORT.md`):
1. Assignment-level activation was ~0 (0–2 platform–target changes per game across B–F), so
   the components mostly never changed the allocation these games ran.
2. Per-seed outcome deltas are direction-inconsistent between consecutive variants and even
   between A (pure W5) and B (≈ same policy): identical-policy runs drew 2-dead-clean vs
   10-dead-defeat on the same seed, matching the verified run-level nondeterminism
   (`coevolution_final/RNG_NONDETERMINISM.md`).
3. Therefore outcome marginal effects (±0.3 to ±2.7 dead at N=3) are within noise and are not
   attributable to any single component.

## Evidence seeds

None can be honestly claimed as "evidence" for a component effect; the largest apparent jump
(B−A prediction, +2.7 mean loss) is contradicted per-seed (s4002 B improved over A) and by the
B≈A policy equivalence, so it is treated as noise, not as a prediction effect.

## Bugs found

- `handoff_count` / screen-evaluation counters were contaminated by the (ignored) dev2
  collapse-allocation that previously ran inside `W6DecisionCore.step()` during dev3/iso runs.
  Fixed by routing dev3/iso through a new `features()` path that performs no allocation
  (`anti_evasion/w6_harness.py`, `agent_hybrid_w6.py`). Decision-neutral (assignment was
  already recomputed by `allocator_centric`), metrics-hygiene only. See `BUG_FIX_LOG.md`.

## Conclusion for the allocator

At the studied activation level there is **no measurable allocator marginal** to blame; the
remaining S2 dev3 losses vs W5 are dominated by run-level nondeterminism on hard seeds and by
near-zero mechanism activation, not by a specific allocator component.
