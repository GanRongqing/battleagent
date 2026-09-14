# Shadow Audit Design
Decision-neutral protected-SOFT shadow. Real policy frozen to W5: agent runs W6_MODE=dev4_2 +
W6_SHADOW_ONLY=1 => allocator output = base_alloc passthrough, no execution override, no
task changes; a pure `_shadow_log` computes WOULD_REASSIGN under the minimal trigger
(SOFT, not near-lock(dist<LOCK_RANGE), not unique feasible interceptor, coverage-safe,
current risk < HIGH, best alternative risk >= HIGH) and logs only.
Rule: reason = PROTECTED_SOFT_PRIORITY_INVERSION.
