# 02 — C14 COVERAGE_FLOOR_SCREEN (change + result)
File: `agent_hybrid_coverage_floor.py` (white-combat-0014-v1, parent **C10**).
Mechanism (ONE): during `MISSION_GLOBAL_REACQUIRE`, spread available USVs across the fleet's **own initial
y-band** (recorded from the first observation, legal own-history) instead of each holding its own y, so both
flanks stay covered. No scenario/route/strategy ID, no truth.

## Targeted run (W2-5, seed 43001, identity VERIFIED, route1)
| version | Kills | Losses | Breakthrough | Result | Endgame White y (alive) |
|---|---|---|---|---|---|
| C10 | 27 | 14 | 1 | Defeat | −142…−73 (all south) |
| **C14** | **27** | **14** | **1** | **Defeat** | **−180,−108,−36,+36,+108,+180** (both flanks) |
- C14 **did change behaviour** (endgame positions spread and trajectory hash differs: C10 `384b46b27af4` vs
  C14 `a30d84bbb200`) — so this is **not** a silent no-op like C13.
- But the outcome is unchanged: still 27/14, 1 breakthrough, Defeat.

## Interpretation
- Spreading coverage so a USV sits near the north lane (e.g. y≈+36 vs the dasher lane y≈+55, ~19 km) puts
  the dasher inside radar/lock range, yet White still cannot stop it. With the engine timeline (each kill
  needs two ≥300 s completed lock windows, plus closure) and the final leg at **10 m/s**, the interception
  window is too short once the dasher is already near x≈120 km.
- => The binding constraint is **endgame interception time**, not merely which y-band is covered.
  Coverage floor is necessary but not sufficient.
