# W6 DEV Report — Component Sanity (Round 1)

## Setup
White 5+5 vs Black 10, opponents B0/B3, paired DEV seeds 2001-2003, W5 (frozen V5) vs
W6 (anti_evasion layer). 12 episodes. DEV seeds only.

## Results (component_sanity.csv)

| opp | seed | W5 result | W5 usv_dead | W6 result | W6 usv_dead |
|---|---|---|---|---|---|
| B0 | 2001 | V clean | 1 | V clean | 0 |
| B0 | 2002 | V clean | 3 | V quirk(brk) | 5 |
| B0 | 2003 | V clean | 3 | V clean | 0 |
| B3 | 2001 | V clean | 0 | D | 5 |
| B3 | 2002 | V clean | 1 | V clean | 2 |
| B3 | 2003 | V quirk | 0 | D | 2 |

- W6 B0 clean 2/3 vs W5 3/3 (one quirk-victory, breakthrough=1)
- W6 B3 clean 1/3 vs W5 2/3+quirk (2 W6 defeats)
- W6 mechanism fire: predictive_intercept YES (3891), adaptive_screen YES (496),
  breakthrough_horizon YES; **handoff=0, track_maintenance=0 (inert)**.

## Conclusion (per task §26 rule)
W6 on B0 regressed >20pt and on B3 is worse → **STOP full DEV; audit mechanism bug**.
See W6_DEV_HISTORY.md round-2 plan (handoff trigger, intercept standoff, B0 quirk).
W6 is NOT ready for the 3-scale DEV or holdout.
