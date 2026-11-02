# 07 — C30 INTEGRITY TEST (post-cleanup)
- Imports OK: agent_hybrid_v5, budget_gate, press_search, fleet_recon, safe_recon, split_screen, adaptive,
  universal_safety, adaptive_skills; C30 constructed (`SplitScreenController` + `FleetTetheredUAVManager` +
  `BoundaryAwareSafety`).
- Unit tests: adaptive 6/6, universal_safety 5/5, split_screen 4/4, fleet_recon 3/3.
- In-place compiled extensions present: `hsystem/simulation/**/*.so` (5).
- Smoke episode (real engine, post-cleanup): **W2-2 C30 seed 43001 = 30/8, valid=True** — matches the E26
  reference. Cleanup did not alter behaviour. VERIFIED.
