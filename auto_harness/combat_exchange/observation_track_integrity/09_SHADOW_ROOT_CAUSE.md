# 09 — C11 SHADOW DISCREPANCY ROOT CAUSE
Question: why did the raw game-log shadow show engagement while the agent's `_engaged` did not?
- The earlier quick shadow (c11_fast_iteration) MIXED W2-4 and W2-6 package logs (both were in worker
  dirs) → its "8/14" is not a clean W2-6 statistic (methodological error, classification CLOCK/
  methodology, not a pipeline bug).
- For the TRUE W2-6 FORM events (t=25290 support white_usv16; t=26670 support white_usv15):
  - game-log `active_enemies` contains usv18 at 34 km / 15 km → engaged.
  - agent `obs.active` ALSO contains usv18 at the same position (**identical**).
  - agent `tracks` does NOT contain usv18 (suppressed via `killed_names`).
  → the gate `_engaged` (which reads `tracks`) returns False → C11 == C10.
Root cause = **TRACK_MANAGER_BUG** downstream of a fully-intact legal observation.
NOT shadow truth contamination (the shadow used legal data); NOT API/parser loss.
