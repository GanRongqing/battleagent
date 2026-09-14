# W7 Fastpath Report

## Profile (read-only, from live W5 logs 4001-4005)
- The agent makes ~1 decision per ~30-s sim macro step (est. decisions = sim_time/30,
  ~500-1100 per episode) and completes each cycle in ~0.4-0.9 s wall (episode wall 380-470 s).
- The engine advances on an apply/release macro cadence (MACRO_STEP ~30 s sim); the agent
  responds well inside the window. Continuous-engine timing variance (R1/R3) is cadence-level,
  not agent-CPU-level.

## Decision
Policy-equivalent micro-optimization of the W5 hot loop has negligible expected latency /
sim-time-slip benefit because the agent is already ~0.5 s/cycle against a ~30 s sim macro.
Per prompt §13 (latency gate not met) FASTPATH = DROP without spending sim episodes.

Files: fastpath/FASTPATH_PROFILE_BASELINE.{md,csv}
