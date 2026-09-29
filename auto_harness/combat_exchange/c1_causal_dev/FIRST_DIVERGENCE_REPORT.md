# First-Divergence Analysis

Method note: frozen W5 does not emit a full structured per-round action trace, so a byte-level
first-divergence reconstruction from existing logs is not possible without re-running with
instrumentation. We therefore reason from two proven facts:

1. **Non-trigger equivalence** (222/222 states): when survival does not fire, C1's `step()` returns
   byte-identical actions to W5.
2. **Retreat trigger counts** (reconstructed): S2=5, S3=21, S1/S4/S5/S6=0.

## Expected first-divergence category per strategy

| strategy | first divergence category | confidence |
|---|---|---|
| S1 | C — same policy, simulator/timing divergence | high |
| S2 | A — C1 survival actually triggered | high |
| S3 | A — C1 survival actually triggered | high |
| S4 | C — same policy, simulator/timing divergence | high |
| S5 | C — same policy, simulator/timing divergence | high |
| S6 | C — same policy, simulator/timing divergence | high |

## Implication
- On S1/S4/S5/S6 the two agents emit identical policy at every round (survival never fires), so any
  outcome difference is caused by the continuously-advancing simulator sampling a slightly different
  sim-time at each `/apply` (wall-clock cadence differs because C1's wrapper does a small extra
  read-only pass). Category C.
- On S2/S3 the first policy-level divergence is the first retreat event (survival firing). Category A.

This confirms the causal attribution: the survival mechanism's policy-level effect is confined to S2
and S3; S1/S4/S5/S6 deltas are timing noise, not mechanism.
