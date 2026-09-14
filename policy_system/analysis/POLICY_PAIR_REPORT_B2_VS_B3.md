# B2 vs B3 Pair Report
- Artifact: black-b2-v1 (bundle 5834...) vs black-b3-v1 (bundle 7406...) -> DIFFERENT (distinct
  entry/profile identity; same code file but profile + runtime entry differ and are part of the
  bundle).
- Declared semantics: families coordinated_pressure vs adaptive_multi_axis_penetration;
  declared_traits differ (coordination high-static vs high; adaptivity none vs high;
  recon_dependency none vs high). B3 trigger_and_switch present (60km White proximity lane
  shift; 15s replan tick with heading anti-spam); B2 has none (static).
- Empirical: NO valid B2 tournament logs in repo (legacy smoke INVALID due to profile-import
  bug; excluded). => INSUFFICIENT_EVIDENCE. No fabricated B2 behavior claimed.
- Verdict: SEMANTIC difference present; empirical distinction NOT yet validated (need a valid
  B2 calibration batch under frozen W5 before admission evidence).
