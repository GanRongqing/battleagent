# 07 — TRACK MANAGER INTEGRITY
Faithful behaviours (confirmed):
1. legal positioned observation → creates a track with `has_position=True` (test_live_contact_is_tracked).
2. repeated observation → updates the same track.
3. bearing-only (passive) → track with `has_position=False`; no position fabricated (test_2).
4. freshness uses the same `obs.now` (engine time).

**DEFECT found (data integrity):** `TrackManager.update` (l.474-475) does
`if name in self.killed_names: continue` — a name in `killed_names` is **permanently suppressed**, even
when the legal radar observation keeps reporting it `active` **with a position**.
`kill_detect` (l.537-560) populates `killed_names` from heuristics (`engaged_missing` when a Black-kill
delta occurs; `stationary_duration >= CORPSE_AGE` corpse test) that **false-positive on living enemies**.

Evidence (W2-6 seed 43001, logging-only replay, 1119 steps):
- 10 `[KILL]` events fired for enemies that remain in `obs.active` (usv11,12,13,14,16,17,18,19,20,21).
- **892 / 1119 steps** have at least one `obs.active` positioned contact absent from `tracks`.
- **4042** active-but-untracked unit-steps; usv17 suppressed for the whole episode (892 steps), usv19 880,
  usv20 869, usv18 276.
- At the C11 FORM step (t=25290) `obs.active` contains usv18 @ (136.7,0) 34 km from white_usv16, but
  `tracks` does not contain usv18 → the controller cannot treat it as engaged.

Impact: the agent fights substantially blind to enemies its own legal radar still reports.
