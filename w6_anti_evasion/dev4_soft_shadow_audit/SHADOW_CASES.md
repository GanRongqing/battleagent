# Shadow Cases (heuristic, from unique opportunities)
Heuristic verdicts (decision-local; no episode outcome used):
- STRONG_GOOD (upper bound) = opportunities stable >=600 s (32; ~20% of 156) with LOW/MED->HIGH
  risk inversion and no protection violation.
- PLAUSIBLE = stable 300..<600 s (~20).
- TRANSIENT = <600 s (~104); mean opportunity duration ~302 s -> most proposals decay quickly.
- BAD = 0 (no near-lock/unique/coverage violations in any proposal by construction).
Note: full case-level tactical scoring requires richer per-case fields; treat counts as
heuristic, not validated STRONG_GOOD labels.
