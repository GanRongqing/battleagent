# 02 — PASSIVE CONTRACT FIX (structured, platform-bound)
`PassiveHistoryManager` records, per passive alert: `{t, bearing, detected_by, detector_pos (the observer's
own position at that instant), source}`; bounded per-target history (cap 64), duplicate `(t,bearing,detected_by)`
suppressed, expiry enforced in `localize_candidates` (age ≤ 600 s). It refreshes `bearing`/`last_seen_time`
for existing bearing-only tracks but **never** sets `has_position` (no fabricated coordinates). No truth.
Unit tests (`test_passive_isolated.py`) 10/10: multi-detector binding, expiry, duplicate, no-position,
episode isolation, RETURN/LANDING not overridden, no eligible scout → unchanged, SEARCH scout selected,
no candidate → unchanged, single UAV → unchanged.
