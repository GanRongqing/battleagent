# 02 — Sensor / Weapon Source Audit

- White lock/engagement distance is defined in the AGENT (`LOCK_RANGE=40_000`), with standoff band
  29.5–36.5 km (`LOCK_BAND_*`). The engine's `Locker` (arsenal/locker.py) implements `is_locking(target)`
  and `locked`/`locked_info`; Black uses the same Locker component (`black_cmd_lock`).
- **Exact engine weapon/fire range and radar detection range were NOT traced to a concrete numeric
  constant in this pass** (the relevant modules are Cython-compiled). Therefore questions A–F
  (sensor/weapon asymmetry) are **NOT_MEASURED** — no guessed distance thresholds used.
- Observed from data (game logs, no inference): both W2-1 and W2-2 victims are `is_locked=true` with a
  non-empty `locked_attacker` list before death, i.e. **Black legally locks White**; the difference is
  White's own lock conversion (below), not (measurably) a sensing asymmetry.
