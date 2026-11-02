# 10 — CAUSAL VERDICT
**Root cause (VERIFIED by controlled ablation):** `universal_safety.BoundaryAwareSafety` uses a HARDCODED W2
operational area (x 0..370.4 km, y ±277.8 km, centre (185,0)). Scale/external scenarios place the fleet at
y≈375–435 km, outside that box, so the layer continuously rewrites all USV/UAV courses toward (185,0). The
fleet leaves the engagement geometry, never obtains active contact or locks, and is destroyed (S10 0/5) or
takes extra losses while still eventually killing (S20 10/8, EXTT 2/5).
Evidence chain:
`observable (own pos y≈405k, hardcoded box ±277.8k) → controller decision (safety rewrite) → action (course to CENTER)
→ no active contact/lock → 0 kills / extra losses → K/L`.
Controlled isolation:
- S10: C10 5/1, C19 5/1, C25 5/0, **C27 0/5**, C30 0/5 → press/tether neutral-or-better; safety causes the failure.
- S20: C10 10/1, **C27 10/8**, C30 10/8 → safety causes +7 losses; split neutral.
- EXTT: C10 8/1, **C27 2/5**, C30 2/5 → safety causes regression; split neutral.
Falsified: H1 (C19 press) — no regression (C19=C10 on S10). H2 (split) — C27=C30. H3 (tether) — C25 best (5/0).
Confirmed: H4 (safety side effect). H5 (state management) — no evidence.
