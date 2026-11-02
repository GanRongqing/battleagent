# 05 — C31 DESIGN (white-combat-0031-v1)
C31 = C30 + `ScenarioAgnosticBoundarySafety` (parent C30). Only the boundary-region source changes:
- Old: hardcoded W2 rectangle (x0..370400, y±277800), CENTER(185200,0), margin 8km.
- New: real public polygon from `obs.public_area`; intervene only if predicted next-step position is outside the
  real polygon, or the unit is already outside, or it is within a 5km near-boundary band AND approaching
  (`d_next < d_now`). Interior motion is never rewritten (no E29 failure mode).
- On a true intervention, steer toward `polygon.representative_point()` (guaranteed interior), preserving speed.
- Covers USV `move` and UAV `fly` after ActionSafety, before /apply. No tactic/engine/rule changes.
- Missing/invalid area → `available=False`, no rewrite, reason recorded (never fall back to W2 box).
