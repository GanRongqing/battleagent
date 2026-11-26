# 07 — FAILURE vs SUCCESS COMPARISON (E34 fair)
Detection/lock gaps are small everywhere (lock ≈ detection+30s). The discriminator is **breaches and late-game
coverage**, not first-contact:
- **Success (F10,F13,F16)**: 0 breaches. F09 has high CER (2.57) but 3 breaches → Defeat. So **positive exchange ≠
  held line**; breach control separates Victory from Defeat even at high CER.
- **Failure (F02,F03,F04,F05,F08)**: all breach-limited (1–10 breaches) with narrow K/L losses. F03 has the most
  breaches (10) — the route's double-wing loop splits White's coverage.
- **F14 (borderline 10/10)**: earliest detection (00:34) and a 1:1 draw; 1 breach tips it to Defeat.
Per-breach unit IDs and last-lock times were not extracted (needs a LOCK_TRACE-enabled re-run) → that sub-item is
NOT_MEASURED; the breach counts and K/L are VERIFIED from the engine result reasons.
