# 03 — C15 PASSIVE_OBSERVATION_RECOVERY
File `agent_hybrid_passive_recovery.py` (white-combat-0015-v1, parent **C10**).
- `PassiveAwareTrackManager`: refresh `bearing` + `last_seen_time` for existing bearing-only tracks, record
  `detected_by` set; never fabricate a position.
- `PassiveLocalizeUAVManager`: when a fresh (<900 s) bearing-only track has a known detector and ≥2 UAVs are
  alive, a single deterministic scout UAV (`white_uav10` if alive) flies along that absolute bearing toward
  the emitter, to let the real radar acquire it. One scout only; USV/lock/fire logic untouched.
No truth, no scenario/route/strategy ID.
