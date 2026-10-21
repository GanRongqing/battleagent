# 03 — C15 RESOURCE PREEMPTION AUDIT (VERIFIED)
`PassiveLocalizeUAVManager.step` (C15):
1. Calls `super().step(...)` (builds all UAV actions/roles), then **unconditionally removes the scout's
   action and appends a fly-to-bearing action**.
2. Scout selected by **fixed name** `white_uav10` (if alive) else the last alive by name.
3. Only guard: `len(alive) >= 2`. **No role check** (RETURN / LANDING / SCREEN / REACQUIRE / CHARGING),
   **no battery-safety check**, **no coverage-loss consideration**.
=> It can override high-priority actions (return/landing/battery-critical) and breaks the controller's
   recorded role vs actual action consistency. This is why C15's diversion cost overall coverage
   (positioned targets 26→21, kills 27→19).
## C16 fix
- Scout chosen ONLY among UAVs whose controller state == `SEARCH` (idle search).
- No fixed UAV name; deterministic by name.
- >=2 alive requirement kept; if no eligible SEARCH scout, original actions returned unchanged.
- Localisation task ends naturally when the target becomes positioned or the bearing is older than
  `LOCALIZE_MAX_AGE=600 s`.
