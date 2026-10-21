# 03 — TACTICAL CHANGES (C12 BEARING_GUIDED_REACQUIRE)
- File: `agent_hybrid_bearing_reacquire.py` (white-combat-0012-v1), parent ACE.
- Single change: while `MISSION=GLOBAL_REACQUIRE`, an AVAILABLE USV receiving a passive bearing alert
  steers along that **absolute azimuth** (80 km aim) instead of the static `SCREEN_X=120 km` line.
- Uses only legal `obs.passive{name,bearing,detected_by}` + own positions; no truth, no route/strategy ID,
  no lock/fire/weapon change. In all other missions behaviour == ACE.
- Rationale: E10 diagnosis showed W2-2 (and W2-1) spend long periods in GLOBAL_REACQUIRE with only passive
  bearings; steering toward the bearing creates positioned tracks and earlier engagement.
