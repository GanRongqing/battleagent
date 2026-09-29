# 06 — Root Cause Report

## Baseline (W5, N=2 × 6 strategies, seeds 11001/11002)
- Overall pooled CER = 131 kills / 180 losses = **0.73** (exchange wins 4/12).
- Best: S1 (horizontal, central convergence) CER 2.47. Worst: S5 (diamond, same route) CER 0.11.

## Kill-chain failure classification (non-killed detected targets, N=160)
| class | count | % |
|---|---|---|
| KC-F1 DETECTED_NOT_COMMITTED | 138 | 86.2% |
| KC-F5 ATTACKER_DIED_BEFORE_KILL | 20 | 12.5% |
| KC-F9 GEOMETRY/STANDOFF | 2 | 1.2% |

Note: F1 uses the step-level `[ASSIGN]` PROXY (frozen W5 has no canonical allocation
instrumentation); used for diagnosis only, labeled as proxy.

## White death audit (180 deaths)
- 75% of dead White USVs were committed to a target at some point (`[ASSIGN]`).
- 81% died **without a valid lock** (not actively locking a target at death).
- 39% died **isolated** (<2 friendly USV within 50 km).

## Interpretation (hypothesis, not fixed premise)
1. CER problem is **White USV attrition**, not low kill count. Committed targets are killed
   at high rate; the problem is White USVs die while exposed.
2. White USVs die while **chasing/committed but without a stable lock** — they press targets
   they cannot lock, get exposed, and are destroyed by the numerically superior Black (30 vs 20).
3. This matches mechanism **C. SURVIVAL_AWARE_ENGAGEMENT** (step 10): "no valid lock +
   support too far + enemy pressure high → retreat to support geometry instead of chasing".

## Dominant mechanism
**SURVIVAL_AWARE_ENGAGEMENT (C)** — coverage rationale: the single dominant actionable
failure family is "White dies without a valid lock" (~81% of deaths), which is a survival/
engagement-commitment failure, not a kill-closure failure (committed kill rate is high).

## Explicitly ruled out this generation
- KILL_CLOSURE (A): committed kill rate already high; KC-F3/F4/F6 ≈ 0.
- LOCAL_OVERMATCH (B): not the first lever — the signal is exposure/death, not inability to kill.
- Detection/sensing changes (phase rule 12): detection is NOT the failure (targets are detected;
  the failure is downstream exposure).
