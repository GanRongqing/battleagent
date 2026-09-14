# W6-dev4 Commitment Audit (READ-ONLY)

Grounded in the actual W5 code (`agent_hybrid_v5.py`) + the 2035-state replay dataset
(`dev3/replay_audit/allocator_states.jsonl`). No code changed.

## 1. What currently means "unassigned / free"?
`USVController.classify` (`agent_hybrid_v5.py:1990-2001`): a USV is AVAILABLE iff it is alive,
NOT frozen, NOT locking, and `usv_ctrl.targets[name]` is None. AVAILABLE is the only pool the
W5 `ThreatAllocator` re-assigns (`available = [name for name, trg in usv_map.items()
if trg is None and name in usv_pos]`, `:1807-1808`).

## 2. What means "assigned but not a high-value engagement yet"?
`INTERCEPTING` = alive, not frozen/locking, and `usv_ctrl.targets[name]` set (`:1998`). This is
the natural **SOFT_COMMITTED** class: the platform owns a target but has not locked it.

## 3. What means active lock / frozen / second-hit chain?
- `LOCKING` = `is_locking` and `locking_unit` set (`:1995`) → **HARD**.
- `FROZEN` = `is_frozen` (hit-freeze, ~`FROZEN_DURATION = 300s`, `:77`) → **HARD**.
- Second-hit / damage chain: no separate flag; the freeze window after a hit
  (`FROZEN_DURATION`) is the code's notion of a protected follow-up window → treat as HARD.

## 4. Reusable commitment fields
- `usv_ctrl.targets` (usv → target|None) — the authoritative WHO/TARGET map.
- `usv_ctrl.state` — USV FSM (AVAILABLE/INTERCEPTING/LOCKING/FROZEN/DEAD) via `classify`.
- Per-USV `/status` flags: `is_alive`, `is_locking`, `locking_unit`, `is_frozen`.
- `EnemyTrack.engaged` / `assigned_usvs` — coverage bookkeeping (allocator-only).
- Reserve intent fields: `reserve_ratio` (0.0–0.5, scale-agnostic) / `reserve_usvs`.

## 5. Why ~98% of replay states have no free USV
The replay snapshot's `usv_map` (the live `usv_ctrl.targets`) shows most USVs already hold a
target at each decision (they persist from earlier steps). The W5 allocator only assigns the
truly AVAILABLE subset (`trg is None`), and its reserve is drawn from that same AVAILABLE
subset (`:1855-1866`). In heavy-contact S2/B3 states almost every USV is already committed, so
`available` (and hence the free/reserve pool) ≈ 0. Empirically the free pool exists in only
1.8% of the 2035 states.

## 6. Which committed USVs are theoretically safe to release (soft)
Per the engagement semantics above, a committed USV is safely reallocatable (SOFT) when it is
`INTERCEPTING` on a target it has **not** locked, is not frozen, and its current target keeps
at least one other interceptor (so releasing it does not strand an imminent corridor). Those
that are LOCKING or FROZEN (or the sole interceptor of an imminent target) are HARD and must
be protected from allocator-driven reallocation.

## Consequence
W6 features (prediction/risk) compute fine, but with no AVAILABLE pool and no soft-release
mechanism they have zero platforms to act on. dev4 therefore needs an auditable
commitment-state layer (FREE / SOFT_COMMITTED / HARD_COMMITTED / RESERVE) plus a releasable
pool, all feeding the SAME assignment boundary (WHO/TASK/TARGET) with the legacy controller
unchanged (HOW untouched).
