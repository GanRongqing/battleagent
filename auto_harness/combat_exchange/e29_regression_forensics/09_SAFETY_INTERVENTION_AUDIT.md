# 09 — SAFETY INTERVENTION AUDIT
- Code: `universal_safety.py` hardcodes `AREA=(0,370400,-277800,277800)`, `CENTER=(185200,0)`, `MARGIN=8km`.
- Scale/external scenarios deploy White USVs at **y≈375–435 km** (VERIFIED from step-0 positions), i.e. outside
  the hardcoded box, so `BoundaryAwareSafety` rewrites **every** USV (and UAV) move toward `CENTER`.
- Motion evidence (S10): C10/C25 mean y stays 405 km; C27/C30 mean y 394→372→350→329 km (toward y=0). VERIFIED.
- The rewrite count is continuous; no AREA_OUT crash, but the tactic is destroyed (no contact/lock).
- W2 remains correct only because W2's real area equals the hardcoded constants — the safety is not
  scenario-general. This is the single cross-scenario regression mechanism.
- TRACE ON/OFF equivalence for W2 was verified in E23; here the motion evidence is from game logs (no trace needed).
