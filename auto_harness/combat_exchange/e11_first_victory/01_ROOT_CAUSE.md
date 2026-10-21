# 01 — FIRST-VICTORY ROOT CAUSE

## W2-5 (C10, 27/14, 1 breakthrough) — endgame
- `ended_reason` = “敌方1艘艇突破防线”; final: 26 Black radar contacts, 6 White alive, 10 UAV dead.
- Endgame White survivors are all at **x≈120 km, y between −142 and −73 km (south)**; the remaining Black
  are at x>214 km. The breacher never appears as a positioned contact near the end.
- Black names **never positioned** during the episode: usv1, usv2, usv3, usv4 (usv3/usv4 passive-only).
  A Black that slipped around the **northern flank** (uncovered, since all survivors are south) is the
  breach candidate.
=> W2-5 block is a **coverage/force-distribution** issue (north flank left open), not a software defect.

## The decisive software/execution defect: UAV global search flies into the enemy envelope
- W2-5: all **10 UAVs were destroyed in a single step (06:57)**. At 06:56:30 they were at x=212–244 km,
  y=−72…−142 km, **12–30 km from known positioned Black** (usv23/24/26/27/28/29) — i.e. deep inside the
  Black engagement envelope.
- `UAVManager._global_search_fly()` picks the highest-priority **unobserved** cell via
  `CoverageMap.best_unobserved()` and flies there, **without any threat consideration**. The cell was
  occupied by Black → the unarmed UAVs were mass-killed.
- Same pattern explains W2-1's early UAV wipe-out (all UAVs dead by ~14.9 ks, long before the engagement).
=> Classification: **Maneuver/Execution failure** (search target selection ignores known threats).
  Not engine truth, not a logging artefact.

## Consequence
Losing all UAVs early removes the forward sensor layer → in W2-1 the remaining Black are known only as
passive bearings → no positioned tracks → no own-lock → 0 kills. Fixing UAV survivability is the highest-
value lever for the first Victory.
