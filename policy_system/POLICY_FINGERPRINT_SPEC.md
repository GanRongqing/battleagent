# Fingerprint Spec (fp-v1)
Features (log-derived; availability flagged, proxy marked where approximate):
- first_detection_time (meta), first_lock/contact proxy, first_kill, resolution_time
- lost_track_runs (log step proxy), capacity_hole_proxy_steps (visible-not-engaged proxy),
  reacquire_attempts
- response_signature: clean/breakthrough/defeat rate the opponent induces on the frozen White
  baseline.
Each numeric feature stores mean/median/std/n. Spatial/replan/formation features are NOT in
fp-v1 because available opponent logs do not carry per-ship geometry/replan events
(unavailable, not zero). Scenario-conditioned: compute per scenario set; seed sets recorded.
Logs hash ties each fingerprint to its source logs.
