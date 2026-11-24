# 03 — ENVIRONMENT MANIFEST
- Policy: C31 `white-combat-0031-v1` (entry `agent_hybrid_c31.py`; safety `scenario_agnostic_safety.py`, BUFFER=5000).
  Hashes (sha256-16): c31 `3f2ee050f3631a89`, safety (with counters) see E31 manifest; engine `a509457250bc2799`.
- Baseline commit: E31 `178260f` / E32 `58d3e23`. This round adds only scenario configs + an additive
  `red_formation` mode (`horizontal_N`) — existing modes unchanged (verified: horizontal→20+10, diamond→20+10).
- Runner: E9 identity + E15 manifest, workers=3, AREA_TRACE + SAFETY_TRACE (default-off engine diagnostics).
- Public area: judge polygon via `/status.公开地图.作战区域` (same W2 map). No scenario-ID branching anywhere.
