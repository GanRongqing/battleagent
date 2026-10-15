# 01 — LOCK ENGINE SEMANTICS (from source: `hsystem/simulation/arsenal/locker.py`)

## Two distinct states per unit
- **Outgoing (`self.locking`, `self.locking_name`)** — this unit is locking a target. Set by
  `Locker.is_locking(p)` (only if not already locking). Cleared by `_locking_work()` when the target is
  gone, the distance ≥ 40 000 m, or `target.locker.locked_times >= 2`; also cleared externally when the
  target's own 300 s window fires (`emy_unit.locker.locking = False`, line 115).
- **Incoming (`self.locked_info[enemy]`, `self.locked_times`)** — chains from enemies locking THIS unit.

## A1 — exact meaning of `locked_times`
`_locked_work()` (called every engine tick via `_lock_work`, `implement()` line 216):
1. For each incoming chain (enemy E → this unit X):
   - if `distance(X,E) >= 40_000` → mark `locked=False` (out of range; no hit). (line 109)
   - else if `engine.time - locked_begin_time > 300` → mark `locked=False`; clear `E.locker.locking`;
     draw hit `_stable_rand(X.name, E.name, int(time)) > 0.2` (~80% hit); on hit
     `locked_times[E] += 1`, `frozen=True`, `frozen_time=time`. (lines 112–123)
2. `self.locked_times = min(2, sum(locked_times over all incoming chains))`. (line 126)
3. `if sum >= 2: kill home_unit` (+ one carried plane). (lines 127–133)
4. Frozen units persist 300 s (`frozen_time`), then unfreeze. (lines 135–139)
5. `frozen` freezes the motor + turns the radar off. (lines 142–149)

**Answers:**
- Increment: once per **completed incoming lock window** that also passes the ~80% hit draw.
- Not per tick: it is gated by a **continuous 300 s** window and the hit roll.
- Time threshold: **yes, 300 s** (`locked_time > 300`).
- Multiple enemies: **yes** — `sum` over all `locked_info` entries; two different enemies can each
  contribute one hit.
- Counter reset: `locked_times` is monotonic (never decremented); `locked` (the chain window) resets.
- One lock → multiple counts? No — one completed window → at most one hit.
- Kill trigger: `sum(incoming hits) >= 2`.

## A2 — the 300-second condition
**CONFIRMED as an ENGINE rule** (`locker.py:113` `if locked_time > 300:`). It is NOT a strategy constant,
NOT the macro-step (which is 30 s), and NOT a log artifact. A lock must be **held continuously ≥300 s**
(10 macro-steps) to produce a hit attempt; a hit then **freezes the target for another 300 s**.
=> `NOT_MEASURED` does NOT apply here; the condition is in readable source.

## A3 — kill also destroys one plane
On the 2nd incoming hit the victim's first plane (if any) is also killed (lines 128–131).

## Implication for the funnel
White killing a Black USV requires **two completed 300 s windows** on that Black (each ≥300 s continuous
lock in ≤40 km + ~80% hit). Therefore a kill needs ≈600 s of effective, in-range, continuous locking,
and the target, once hit, is frozen 300 s (cannot flee but also cannot be re-locked by a different unit
that was out of range). This is why **concurrency** (multiple windows running in parallel) drives the
kill rate, and why a single hit (freeze) is very costly to the victim.
