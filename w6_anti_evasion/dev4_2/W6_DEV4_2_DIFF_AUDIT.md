# W6-dev4.2 Diff Audit
Changed: anti_evasion/config.py (W6_MODE=dev4_2, DEV4_2, REQUIRED_IN_TIME_HIGH=1,
REQUIRED_IN_TIME_CRITICAL=2, CRITICAL_RISK=0.9), agent_hybrid_w6.py `_dev4_allocate`
(dev4.2 pre-pass: capacity-deficit + deadline + coverage-safety, reason
FREE_TO_IMMINENT_CAPACITY_DEFICIT), metrics.py counter dev4_capacity_reinforce_events.
Behavioral change: FREE->imminent eligibility uses capacity/deadline/coverage, NOT ETA ratio.
Unchanged: SOFT/HARD/reserve/handoff/weights/controller/HOW; execution override 0.
