# 03 — PLATFORM CAPABILITY PARITY (VERIFIED by building E34-路线01 in-process)
- USV radar: White 30 km == Black 30 km (`u.radars[0].attr.distance`, with HSYSTEM_WHITE_USV_RADAR=30000). **PASS**
- USV max speed: 20 == 20. **PASS**
- Weapons / lock time / hit probability / freeze / health: both sides use the SAME engine components
  (`locker.py`, same `RadarWithGuider`), so rules are identical by construction. **PASS**
- UAV: **0 on BOTH sides** (the original scenarios have no UAVs). Parity is trivial (0==0). **PASS** (N/A-equipment)
- Control period / step mode: same engine & MACRO_STEP for both. **PASS**
- The White-radar change is a scenario-level config via env override (default unchanged = 20 km); no engine
  detection algorithm, weapon, or physics rule was modified. **PASS**
