# W5 Loss Analysis — Phase 0 corpus (100 episodes, S2 x B3_ADAPTIVE, seeds 6001-6100)

## 1. Outcomes
| outcome | n | black_breakthrough | enemy survivors | friendly loss | resolution (mean) |
|---|---|---|---|---|---|
| CLEAN_WIN | 65 | 0 | 0.00 | 3.1 | 19963 |
| BREAKTHROUGH_WIN | 26 | 1 | 0.00 | 4.2 | 39162 |
| DEFEAT | 9 | 1 | 1.33 | 5.2 | 30688 |
| **all failures** | **35** | **1.00** | 0.34 | 4.4 | 36983 |

Every one of the 35 failures has **exactly one breakthrough event**. In 26/35 White still
kills all 20 enemies (the leaker is killed *after* crossing); in 9/35 White also loses >=5
USVs and 1-3 enemies survive.

## 2. What does NOT explain the losses
- Detection/kill-chain onset is identical: first_detection 1855.6 vs 1855.7 (d=0.01),
  first_lock 7420 vs 7407, first_kill 8333 vs 8343.
- **Track-continuity metrics are a duration artifact, not a cause.** Raw counts are higher in
  failures (lost_track_runs 9.1 -> 11.8; capacity_hole 26.1 -> 32.7; reacquire 175.8 -> 208.1),
  but failures last ~2x longer. Normalized per 1000 steps / per 1000 sim-s the failure rates are
  **LOWER** (lost_track x0.60, capacity_hole x0.56, reacquire x0.54). The earlier provisional
  "track continuity is the dominant target" reading was a counting confound.
- Absolute-time binning of visible/lost tracks in overlapping windows (0-5k, 5-10k, 10-15k,
  15-20k, 20-25k sim-s) is nearly identical clean vs fail. The difference is only that failures
  keep running past 25k with no visible tracks.

## 3. What DOES explain the losses
The failure signature is **one leaker crossing the break line**, and the battle then dragging:
- resolution clean 19963 vs fail 36983 (d=3.91); resolution>30000: 0% clean vs 88.6% fail.
- post-last-kill tail clean 3780 vs fail 14768 (breakthrough-win tail 16446).
- survivors 0.00 clean vs 0.34 fail; friendly loss 3.1 vs 4.4 (d=0.77).
- failures explored slightly more area (102.9k vs 93.7k km2), consistent with over-extension /
  a thinner defensive front.
- logistic fit is separable; the discriminative axis is "battle drags past ~30k with a leaker",
  not sensing quality.

Mechanistic reading (consistent with B3 behavior): B3 adaptive lanes shift/disperse away from
detected White. A fixed/forward-committed White frontage opens a lateral gap; one enemy uses it
and crosses the break line. White then needs a long cleanup, and if attrition is high (9 cases)
it also loses the attrition battle.

## 4. Failure sub-modes
- **F-LEAK (26, BREAKTHROUGH_WIN)**: containment leak; attrition won, timing lost.
- **F-ATTRITION (9, DEFEAT)**: leak + high friendly loss (5.2) + 1-3 survivors.

## 5. Improvement plan (for a NEW White version; W5 stays frozen)
Priority 1 — containment / leaker prevention (covers 26/35 and all 35 leakers):
1. **Break-line screen**: dedicate a small element (1-2 nearest USVs) to guard the band
   x in [BREAK_X, BREAK_X+40km] instead of committing the whole force forward.
2. **Leaker prediction & preemption**: for each track, project forward motion; if ETA to the
   break line < threshold, preempt lower-priority engagements and re-task nearest USV + UAV.
3. **Dynamic frontage reallocation**: follow the enemy's lateral mass (B3 lane shifts) instead
   of fixed lanes, with overlap so a shift cannot open an uncovered gap.
4. **Cap forward over-extension**: bound pursuit distance; keep a reserve on the threat axis
   (failures explored ~10% more area -> thinner front).
Priority 2 — attrition (covers 9/35):
5. Keep a reserve and avoid chasing B3 into concentrated-fire threat radius; reposition after
   locks break to cut friendly loss (5.2 -> <=3).
6. Concentrate on finishing the last survivors (the tail is 4x longer in failures).
Priority 3 — measurement (do NOT patch on the old target):
7. Fix the miner: normalize features by duration and classify F-LEAK vs F-ATTRITION. Re-run
   Phase-1 targeting; track-continuity/reacquire should not be the primary target.

Acceptance KPIs for Phase 1: leaker rate (fraction of episodes with >=1 breakthrough)
35% -> <15%; resolution and friendly loss not worse. Validate on fresh harness seeds.

## 6. Caveats
- W5/B3/physics frozen; this is analysis + proposal only.
- Breakthrough is registered even if the leaker is later killed; "enemy_kills=20" therefore
  does not imply containment.
- The corpus is S2/B3 only; leaker behavior may differ vs other opponents/scales.
