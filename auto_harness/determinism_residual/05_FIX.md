# 05 — Fix applied

## Change (one line, ordering only)
`hsystem/simulation/arsenal/judge_system.py`, `set_units`:
```python
- self.units_all = self.units.copy()
+ self.units_all = sorted(self.units, key=lambda u: getattr(u, "name", ""))
```
`self.units` remains a `set` (membership semantics unchanged). Only the **iteration order** of
`units_all` changes: from address-dependent set order to a stable name-sorted order.

## Why this is legal under the phase rules
- It changes ONLY deterministic entity ordering; no combat physics, sensor semantics, weapon rules,
  agent behaviour, scenario behaviour, ranges, or timing constants are touched.
- The previous order was already non-deterministic (memory-address based), so there is no canonical
  order being overridden; the fix makes the previously-random order stable.

## Verification
- 3 × same-seed runs, t=0/30/60, order-dependent action (`legal_actions["[move]"][0]`):
  `diff_counts = {t0:0, t30:0, t60:0}` → **identical**.
- 3 × 30-macro-step runs (`determinism_test_rel.py`): `first_hash_divergence = None`
  (STATE-IDENTICAL), `first_rel_time_divergence = None`.
- normal mode (`DETERMINISTIC_STEP_MODE=false`): start/status/stop OK (no regression).

## Caveat
The fix makes the previously-random iteration order deterministic; the *mean* combat outcome may
shift slightly versus the old random order. This is expected and is not a physics change. All C4/ACE
numbers in Stage B are produced under this fixed order, so they remain internally comparable.
