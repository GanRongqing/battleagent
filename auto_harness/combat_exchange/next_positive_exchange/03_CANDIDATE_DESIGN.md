# 03 — CANDIDATE DESIGN: C9 TASK_DEMAND_GATED_COORDINATION

- File: `agent_hybrid_demand_gate.py` ; id `white-combat-0009-v1` ; parent **ACE**.
- Single semantic diff vs ACE: reuse C7's bounded 2-unit synchronized-lock package, but **FORM only if
  the target's single owner is currently under hostile lock** (`is_locked` or non-empty `locked_attacker`).
- Applies to: exactly-1-owner targets with an in-range free support, owner not yet locking, owner
  hostile-locked. Exit: member locks / target gone / `MAX_SYNC_TIME` -> DISSOLVE -> ACE fallback.
- Fallback: no eligible target -> behaviour identical to ACE (no redirection, no slowdown).
- Non-trigger equivalence: `test_5` asserts base actions are preserved when the gate is closed.
- Deterministic: support chosen by (distance, id).
- NOT specialized by strategy name; no truth; sensors/weapons/physics untouched; one mechanism only.

Difference vs C7: C7 forms whenever a single owner lacks own-lock (transient healthy state included);
C9 additionally requires verified local demand (hostile lock), removing interference on W2-4.
