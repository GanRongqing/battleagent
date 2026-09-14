# Decision Neutrality
With SHADOW_ONLY, the allocator branch returns base_alloc and no W6 override/realloc code
runs (guarded). _shadow_log only reads legal state and appends a JSON line. Therefore real
allocator output with shadow ON is identical to W5 (same base_alloc -> same USVController).
Offline determinism: shadow predicates are pure functions of saved legal state; unit-level
neutrality verified by construction (no writes to usv_ctrl/targets/apply). Same-state
determinism PASS (pure), hidden-truth PASS (no hidden fields read).
