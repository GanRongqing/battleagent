# 01 — PASSIVE OBSERVATION DATA-CONTRACT AUDIT

## Source chain
`main.py::_build_enemy_intel`: for each White unit's `locked_attacker`, if the attacker is not already in
`active`, append `{name, bearing=_r2(relative_orientation[i]), detected_by=unit.name, source:"被动告警"}`.
`relative_orientation` is the engine's **absolute azimuth** `alg.geo.azimuth(unit.coords, attacker.coords)`
(tzb_engine.py:74). So `bearing` is a valid absolute bearing and `detected_by` is a real friendly platform.

## Confirmed defect (TrackManager.update passive branch)
```python
for p in obs.passive:
    name = p.get("name","")
    if not name or name in seen: continue
    seen.add(name)
    if name not in self.tracks:          # only on FIRST alert
        t = EnemyTrack(name, now); t.bearing = p.get("bearing"); self.tracks[name] = t
    # NO update of bearing / last_seen_time for an EXISTING bearing-only track
```
Consequences (unit-tested, `test_passive_contract.py`):
1. **Stale bearing**: a later alert never updates `bearing` (test_1 shows base keeps 90° when a new 45° alert
   arrives). VERIFIED.
2. **Stale freshness**: `last_seen_time` is not refreshed, so `age` keeps growing (though the name stays in
   `seen`, preventing the drop while alerts persist).
3. **No detector memory**: `detected_by` is not retained after creation (no field; EnemyTrack uses __slots__).
4. **No decision use**: bearing-only tracks are never used by USVController/allocator/UAV scheduling (they
   require `has_position`), so a passive-only enemy can never be engaged. VERIFIED (W2-5 usv4: 0 active, 10
   passive, never assigned/locked).

## Fix (C15, in a TrackManager subclass — base class untouched)
`PassiveAwareTrackManager` refreshes `bearing` + `last_seen_time` for existing bearing-only tracks, records
the `detected_by` set, and **never** promotes them to `has_position=True` (no fabricated coordinates).
`test_passive_contract.py` 5/5: bot-bearing refresh, no-position promotion, detector memory, episode isolation.
