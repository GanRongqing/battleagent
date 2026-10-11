# 05 — LOCK FUNNEL DEFINITION (measurement method)
Stages measured per White combat USV, from the **simulator game log only** (no truth, no new sensors):
1. FRESH CONTACT  — unit alive with a position and `active_enemies` present; distance via positions.
2. LEGAL LOCK OPPORTUNITY — proxy: min distance to an active contact ≤ 40 000 m (the agent's
   `LOCK_RANGE` constant, `agent_hybrid_v5.py`). **The engine's true lock eligibility is
   NOT_MEASURED** (Cython); the 40 km figure is the agent-side pre-filter, not the engine condition.
3. LOCK REQUEST — a per-step `actions` entry containing `锁定` for that unit.
4. LOCK ACCEPTED — that action's `成功 == True` (API/engine accepted).
5. ACTIVE OWN LOCK — `usv_states[].is_locking == True`.
Caveats:
- `is_locked` / `locked_attacker` describe the **enemy locking White** (incoming), NOT White's lock
  ability — treated separately.
- `passive_enemies` carry a `bearing` only (no position) → cannot yield a lock; counted as no fresh
  positional contact.
- `locking_unit` is **not** a field in the game-log `usv_states`; `is_locking` alone is the own-lock flag.
