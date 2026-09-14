# POLICY_SYSTEM_DEMO

B2 card (declared): coordinated_pressure adaptivity=none
B3 card (declared): adaptive_multi_axis_penetration adaptivity=high triggers=2
B3 fingerprint fp-v1: episodes=93 response={'episodes': 93, 'clean_rate': 0.828, 'breakthrough_rate': 0.172, 'defeat_rate': 0.054}
B0 fingerprint fp-v1: episodes=93
B0 vs B3 compare: dist=1.2316 verdict=EMPIRICALLY_DISTINCT
top feature deltas:
  first_detection a=1849.4 b=1852.18 ndelta=-0.317
  first_lock a=7385.34 b=7441.85 ndelta=-1.363
  first_kill a=8312.13 b=8370.25 ndelta=-0.793
  resolution_time a=13421.68 b=21839.26 ndelta=-1.16
  lost_track_runs a=4.22 b=10 ndelta=-1.5

---
## fp-v2 Common Calibration (S2, W5, seeds 7001-7010)

GET /policies/black-b3-v1/fingerprint/latest
  -> fingerprint_version=fp-v2  episode_count=10
     behavioral groups: temporal / spatial / coordination / adaptation
     response: white_outcome (separate from behavior)
     adaptation.adaptive_replan_count.mean > 0 (real B3 runtime events)

GET /policies/black-b2-v1/fingerprint/latest
  -> fingerprint_version=fp-v2  episode_count=10
     adaptation.adaptive_replan_count.mean = 0 (true zero: B2 has no replan mechanism)

GET /policies/black-b1-v1/compare/black-b2-v1
  -> behavioral distance ~0.371, response distance ~0.414
     top behavioral effect: spatial.mean_group_spacing_km d=1.147 seed-consistency=0.7
     verdict = INCONCLUSIVE   (B1 vs B2 not clearly separated under S2 x 10 seeds)

GET /policies/black-b2-v1/compare/black-b3-v1
  -> behavioral distance ~1.111, response distance ~0.977
     top behavioral effect: adaptation.dispersion_event_count d=11.181 seed-consistency=1.0
     verdict = EMPIRICALLY_DISTINCT   (adaptive behavior empirically validated)

fp-v1 remains queryable; /fingerprint/latest prefers fp-v2. behavior and response
are returned as separate blocks (never merged into one opaque score).
