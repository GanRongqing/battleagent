# Persistence State Machine
Identity = (platform, current_target, alternative_target). Timer (sim_time) accumulates only
while the protected base trigger holds (SOFT, not near-lock, not unique, coverage-safe,
current<HIGH, alternative>=HIGH, legal). Reset on ANY: not-SOFT, near-lock, unique, coverage
unsafe, current becomes HIGH, alternative <HIGH, alt/cur change, invalid, destroyed.
continuous_duration = now - opportunity_start (gaps => reset, no 300+300 accumulation).
Each horizon emits WOULD_EXECUTE once per opportunity. Post-trigger metrics measured on the
frozen trajectory (proxy, not causal): post_stable_{300,600,1200}, reversal, alt-switch count,
post_trigger_lifetime.
