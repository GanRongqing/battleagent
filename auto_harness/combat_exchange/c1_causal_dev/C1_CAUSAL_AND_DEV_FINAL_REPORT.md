# C1 Causal Attribution + Paired DEV — Final Report

## Parent & candidate (unchanged throughout DEV)
- Frozen W5 sha256: `e823e7bed219f4693aa778a838df1400c161f8e7e44001502e5bceb0ae804252`
- C1 sha256: `c2fb48f75b0b1289ca9ded7c1abae54826bb471dd1f620cc93c0b9a4ad173055`

## 1. Non-trigger equivalence
- 222/222 states exact match (100%); 0 mismatches. C1 is a pure survival overlay
  (no CE-F1..F7 contamination).

## 2. First divergence
- S1/S4/S5/S6: category C (same policy, simulator/timing divergence) — survival never fires.
- S2/S3: category A (survival actually fired).

## 3. Causal attribution
- S2 (5 triggers) and S3 (21 triggers) are the only mechanism-triggered strategies.
- S1/S4/S5/S6 outcome deltas (seed 11001) were timing noise, not mechanism.
- Verdict: **PARTIAL_SUPPORT** (mechanism effect only observable, not robust).

## 4. Paired DEV (12101/12102)
- W5 pooled CER 0.796 vs C1 pooled CER 0.708 → C1 worse.
- W5 144 kills / 181 losses; C1 114 kills / 161 losses.
- Only 3/6 strategies improve (S1, S3, S6); S2 catastrophic regression (1.90 → 0.11).

## 5. S2 reproduction
- REVERSED on both fresh seeds (C1 0.21 and 0.00 vs W5 1.81 and 2.00).

## 6. Gates
G1 FAIL, G2 FAIL, G3 PASS, G4 FAIL, G5 FAIL, G6 FAIL.

## Final verdict: **DEV_REVERSED**

C1 (survival-aware retreat) is dropped. It does not produce a stable combat-exchange advantage
and regresses the fan-out case. The seed-11001 apparent gains were timing noise.

## Recommendations (for operator decision)
- **DROP_C1** (recommended): the survival-retreat trigger as implemented is net-negative.
- Do NOT stack KILL_CLOSURE onto C1 (the parent is unsupported).
- The honest bottleneck is now clearer: W5's combat exchange is dominated by large per-seed
  trajectory variance (e.g. S1 W5: 23/4 on 11001 vs 0/20 on 12101). Any candidate must be
  judged on PAIRED fresh seeds, and single-seed "wins" must be treated as noise.

## Frozen W5 changed = NO. C1 changed during DEV = NO. C1.1/C2 created = NO.
