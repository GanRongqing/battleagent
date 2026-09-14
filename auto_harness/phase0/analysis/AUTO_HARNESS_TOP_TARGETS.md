# Auto Harness Top Targets (provisional, N=100)
TARGET 1: Track continuity & reacquire latency (lost-track reduction).
  Failure coverage: 35/35 failures share lost-track runs (coarse).
  Change surface: UAVManager reacquire scheduling / TrackManager continuity (SENSING).
  Evidence: lost_track_runs 9.1 clean vs 11.8 fail; reacquire_attempts 176 vs 208.
  Note: refine miner (latency/secondary) before Phase-1 patch.
TARGET 2: Capacity-hole prevention (visible-but-unengaged) — downstream of #1.
  Coverage: capacity_hole_proxy 26.1 vs 32.7.
TARGET 3: Multi-axis / attrition (pending subcluster confirmation).
Recommendation: run Phase-0.1 miner refinement first; do not patch yet.
