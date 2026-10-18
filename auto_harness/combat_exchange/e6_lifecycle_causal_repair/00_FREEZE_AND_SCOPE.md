# 00 — FREEZE AND SCOPE (E6)
- Base HEAD: `6e4fc95` (main). E6 work on branch `experiment/e6-lifecycle-state-integrity`.
- ACE `7527253c…`, C10 `886577b5…`, C11 `07d1ffa9…`, `agent_hybrid_v5.py` `eb6d5341…`,
  engine `locker.py` `130f9c65…` — unchanged.
- `OBS_TI_REVIVE` default = "0" (OFF). `TARGET_LIFECYCLE_V2` default = "0" (to be added).
- Frozen: ACE/C10/C11 tactics, engine, Black, scenarios, weapon/lock, OBS_TI_REVIVE default.
- Scope: causal trace + state contract + minimal flag-gated bookkeeping patch + tests. No C12, no full epoch.
