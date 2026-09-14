# Black Behavior Instrumentation Audit (READ-ONLY)

Where Black policy runs: inside the SIM process (opponent_profiles.py consumed by scenario
builder); the White agent is a separate process and its logs carry NO Black geometry/groups.
available directly (no change needed):
- B3_ADAPTIVE: B3AdaptiveController writes /tmp/opencode/b3_events.json per game with legal
  adaptive event counters: calls, replan_count, lane_shift_count, dispersion_event_count,
  detected_white_event_count. This is a real Black adaptive-event source (offline sidecar).
- White-side per-episode logs: outcome/timing/reacquire/lost (response signature), used for
  B0-B4 response signature on common seeds.
available as proxy / with minimal logging:
- replan/adaptive for B3 (events above). B0/B1/B2 have NO runtime replan: adaptive counts are
  true 0 (available=true, value 0).
missing (would require sim-side geometry logging — NOT implemented this round):
- per-ship position/route/grouping during flight for all profiles (in-game spatial/coordination
  features: mean pairwise distance, cluster count, arrival sync) -> unavailable in fp-v2.
  Spatial structure can only be described from scenario initial-waypoint generators (declared
  geometry), not in-game behavior. Marked unavailable, not fabricated.
Conclusion: fp-v2 supports (a) B3 adaptive event metrics (replan/lane_shift/dispersion/
detected_white), (b) per-profile response signatures on common seeds, (c) availability flags.
In-game spatial/coordination metrics for all profiles = missing (needs future sim-side logging).
