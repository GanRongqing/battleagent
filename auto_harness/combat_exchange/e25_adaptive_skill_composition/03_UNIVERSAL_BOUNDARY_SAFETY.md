# 03 — UNIVERSAL BOUNDARY SAFETY
`universal_safety.BoundaryAwareSafety(ActionSafety)` runs after `ActionSafety.filter`, i.e. after **all**
tactics (move/standoff/patrol/press/chase/skill handoff) and before `/apply`. For every USV `move` it
predicts the next control-period position (v·31s) and, if that would leave the area (x0..370400, y ±277800,
8 km margin), rewrites the course toward the area centre. Cannot be bypassed by any tactic (unlike C26 which
only wrapped `_move` and missed `_standoff_move`). Lock actions and UAV commands untouched; no physics/rule
changes.
Engine proof (`AREA_TRACE`, C27 six scenarios): **RED USV area-outs = 0** (all 50 AREA_OUT events are
`white_uav*`, i.e. UAVs tethering past x=370 — a separate UAV-side issue, does not affect USV CER).
