# 01 — TRACK_STATE_DEFINITION

Derived ONLY from legal observation + TrackManager internal state (no truth).

| state | definition (observable) |
|-------|--------------------------|
| FRESH | `t.is_visible(now)` true (observed this step) |
| PREDICTED_VALID | not visible, but `has_position` and `age(now) < HIGH_CONF_AGE` |
| STALE | not visible and `HIGH_CONF_AGE <= age(now) < drop_age` (ship: DROP_AGE_SHIP) |
| LOST | removed from `tracks` after `age >= drop_age` |
| REACQUIRED | FRESH again after a STALE/PREDICTED_VALID interval (C5) |
| EXPIRED | C5 REACQUIRE window exceeded (timeout or uncertainty threshold) |

These are the exact predicates used by `EnemyTrack.is_visible` / `age` and `TrackManager.update`
(DROP_AGE_SHIP / HIGH_CONF_AGE) — re-used, not re-defined, so no truth leakage.
