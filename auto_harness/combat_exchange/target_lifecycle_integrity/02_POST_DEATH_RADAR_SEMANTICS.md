# 02 — POST-DEATH RADAR SEMANTICS
**Can a dead enemy still appear in `obs.active`?** — Essentially NO:
- `entity.kill()` sets `isactive=False` (`hsystem/simulation/core/entity.pyx:33-35`).
- Radar detection iterates `engine.actives()` = `[u for u in self._units if u.isactive]`
  (`base_engine.pyx:788`; used at `radar.pyx:261` and `:631`).
- `Radar.targets` also filters `target.isactive` (`radar.pyx:62`).
=> `active_enemies` / `obs.active` with a **position ⇒ the target is alive** (classification:
`DEAD_ENTITY_STILL_OBSERVABLE = NO`; `SENSOR_STALE_CACHE = NO`; `API_STALE_CACHE = NO`).
Residual: a same-tick ordering window (`DESTRUCTION_STATE_LAG`) could list a unit that dies later in the
same tick for at most 1 tick — minor, not a standing source of "ghosts".
Consequence: the E4 "revive" revives **live** targets (TRUE_REVIVAL), not ghosts.
