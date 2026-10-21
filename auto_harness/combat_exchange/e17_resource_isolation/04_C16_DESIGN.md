# 04 — C16 RESOURCE_AWARE_PASSIVE_RECOVERY
File `agent_hybrid_passive_isolated.py` (white-combat-0016-v1, parent C10). ONE mechanism: localise a fresh
bearing-only contact using a **SEARCH-state** UAV only, with structured detector-bound bearing.
- Trigger: fresh (<600 s) bearing-only track with bearing + detector_pos from `PassiveHistoryManager`.
- Resource: alive UAVs ≥2, scout ∈ {state==SEARCH}, deterministic (name order), no fixed name.
- Action: fly along the absolute bearing to `detector_pos + 60 km` (real sensor does the acquisition).
- End: target becomes positioned / bearing expires / scout changes role → no override.
- Constraint: RETURN/LANDING/SCREEN/REACQUIRE/CHARGING never overridden; no truth; no scenario/route ID;
  coordination/lock/weapon untouched; actions still go through the normal /apply + legality path.
