# 01 — Timebase Reconciliation

All logs are stamped with the **simulator absolute clock** T_ABS (`[t=NNNs]`). Episode start
`T_EP=0` at first step. No separate offset exists; the earlier reports mixed a **pooled median** with a
**per-strategy value**:

- causal audit printed WIN/LOSS median first-death = **6270 s** — that is the median over the
  whole 30-episode WAVE2 set (5 of 6 strategies — W2-2/3/4/5/6 — have first death ≈5,970–6,720 s).
- **W2-1 individually dies first at T_ABS = 27,270 s** (verified here from
  `W2-1_seed43001` log). W2-1 is an **outlier within LOSS**; the pooled median masked it.

=> 6270 vs 27270 is **NOT a fixed offset**; it is pooling (all-strategy median) vs W2-1-specific.
Correct W2-1 values: episode ends T_ABS≈29,970 s; first death T_EP=27,270 s (relative to the 270 s
first logged step ≈ 27,000 s into the episode).
