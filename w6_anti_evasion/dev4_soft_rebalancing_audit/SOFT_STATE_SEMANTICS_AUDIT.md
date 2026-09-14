# SOFT State Semantics Audit (READ-ONLY)
From real code (anti_evasion/commitment.py, agent_hybrid_v5.py):
- HARD = not alive OR is_locking(+locking_unit) OR is_frozen. (frozen ~ hit-freeze 300 s = second-hit window)
- SOFT = alive, has a target in usv_ctrl.targets, not locking, not frozen => INTERCEPTING/APPROACHING with a committed target but no lock yet.
- FREE = alive, no target (may be RESERVE if the elastic manager holds it).
Fields usable for tactical progress: distance to current target (usvp vs corridor.current_estimate), LOCK_RANGE (40 km; legacy controller locks below it), plan ETA (prediction), breakthrough risk/b_eta/deficit, assigned count per target.
Near-lock operational definition reused: distance < LOCK_RANGE (the legacy lock-transition band) while not locking -> cutting that platform is expensive.
Unique-interceptor: platform is the only alive non-hard platform whose plan ETA*(1+safety)<=breakthrough_eta for the current target (reuses feasibility semantics).
SEMANTIC ISSUES RECORDED (not fixed): SOFT classification has no assignment-age or near-lock field; a platform just under LOCK_RANGE counts SOFT until it actually locks (see near_lock proxy). Unique/coverage use risk/ETA only, no radar-contribution model (CoverageMap exists but no per-platform coverage-value API -> NOT_AVAILABLE in commitment value).
