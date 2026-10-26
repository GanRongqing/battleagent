# 03 — FORWARD RECON FEASIBILITY (offline; truth never fed online)
At Black's first lock (t=10406): 20 White USVs at centroid **(268, 0) km**; 5 UAVs alive at
x 46–126, y 159–264 km → **220–325 km from the front**, i.e. they cannot see the engagement zone.
Feasibility chain:
`AVAILABLE_UAV` (5 alive, battery 58%) → `REACHABLE_SENSOR_POSITION` (UAV 100 m/s; distance to a forward
tether ~230 km ⇒ ~2300 s ≪ 10406 s) → `GEOMETRY_ELIGIBLE` (UAV radar 60 km, ±30°) → `ACTIVE_CONTACT_POSSIBLE`
(Black are within 40 km of USVs at 10406, so a forward UAV would be within 60 km) → `SHARED_POSITION_AVAILABLE`
(position feeds the shared track set) → `USV_LOCK_ELIGIBLE` (USVs within 40 km can lock).
- AVAILABLE/REACHABLE: **INFERRED** (kinematics from logs) · GEOMETRY: **INFERRED** · feasibility itself:
  **VERIFIED empirically by C25** (forward tether moved White's first lock to 10020 s, i.e. BEFORE Black's).
- Caveat: UAV forward-sector orientation matters; C25 uses a forward tether at fleet y with the UAV heading
  east, which empirically produced early contacts.
