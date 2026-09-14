# W6-dev4.1 Diff Audit

Changed files:
- anti_evasion/config.py : added W6_MODE=dev4_1, DEV4_1 flag,
  FREE_TO_IMMINENT_ETA_RATIO=1.5, EMERGENCY_CONCENTRATION=3 (per-target, scale-agnostic).
- agent_hybrid_w6.py : in `_dev4_allocate`, a dev4_1 pre-pass commits a FREE platform to an
  imminent (risk>=HIGH) corridor when concentration < EMERGENCY_CONCENTRATION and
  ETA(P,C) <= 1.5 * best-lead-ETA(C) (reason FREE_TO_IMMINENT_CORRIDOR), then returns.
  dev4 path unchanged.
- anti_evasion/metrics.py : added dev4_free_imminent_events counter.

Behavioral change: ONLY FREE->imminent eligibility widened under the 1.5x ratio gate.
Unchanged: SOFT/HARD classification, reserve semantics, handoff, weights, hysteresis,
cooldown, controller/HOW, Skill/Prompt/B3/physics. execution override = 0.
