# 08 — REGRESSION ROOT CAUSE (inferred, not fixed in E28)
1. **Unconditional eastward press (C19 inheritance)**: C30 sends all no-target USVs east; in scale/external
   scenarios the Black are moving straight_west/random, so the fleet over-commits and takes many more losses
   while achieving the same or fewer kills. (S15/S20/S30: same kills, +7…+10 losses.)
2. **Fixed `SCREEN_EVERY=3` split**: at 5v5 it leaves only 1–2 screen units and fragments the small fleet →
   S10/S10RW collapse (0 kills, all lost). Scale-adaptive fraction needed.
3. **Fleet-tethered UAV recon** was tuned for W2's long eastern approach; in short random-waypoint scenarios
   it provides less benefit (UAV losses are not in CER but consume recon).
4. Not boundary (Universal Safety applied; no new crashes/identity errors). Not an engine/seed mismatch
   (EngineHash a509457250bc2799, paired runs, actual seed == requested).
STATUS: root cause partially INFERRED from K/L + config; no per-unit SKILL_TRACE captured for E28 →
deeper attribution UNRESOLVED.
