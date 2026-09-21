# LLM-Offline Smoke

Command: `run_single_w5.py` sets `LLM_ENABLED=false` (via run_opponent_formal.run_one).
Result: **PASS** — full episode completed without any LLM provider:
- S2 x B0_RANDOM, seed 1001 → `Result.Victory`, clean=1, enemy_kills=20, friendly_usv_losses=4, sim_time=13663, wall=309s.

Conclusion: W5 does not hard-depend on an LLM when `LLM_ENABLED=false`; the deterministic
TrackManager/ThreatAllocator/USVController/UAVManager path runs standalone. (LLM commander is
optional; `CommanderIntentAdapter` falls back to default intent.)
