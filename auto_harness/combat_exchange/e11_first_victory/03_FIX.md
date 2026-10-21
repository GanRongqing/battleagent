# 03 — FIX: C13 THREAT_AWARE_UAV_SEARCH
`agent_hybrid_safe_uav_search.py` (white-combat-0013-v1, parent ACE):
- Cache known positioned enemy positions from TrackManager each step.
- In `_global_search_fly`, among `best_unobserved` cells choose one ≥ `SAFE_STANDOFF=50 km` from any known
  enemy; if none, choose the cell farthest from the known threats (still makes progress).
- Only legal tracks; no truth/route/strategy ID; all other UAV/USV logic unchanged.
Rationale: 50 km is inside the UAV's 60 km radar but outside the observed 12–30 km kill zone, so UAVs can
still detect while surviving.
