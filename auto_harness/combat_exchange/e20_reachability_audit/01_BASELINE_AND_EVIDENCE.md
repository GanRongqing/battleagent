# 01 — BASELINE & EVIDENCE (E20)
Frozen baseline **e3aeabb** (E19). Reused identity-verified logs: C10 (`e9_B_c10_off`), C17
(`e18_w21_c17`), C18 (`e19_w21_c18`). No new episode run (no candidate; see 06).
Evidence corrections vs E19 (VERIFIED from logs):
- Step interval **dt = 30 s**; "2 active steps" = a **60 s** active window (01:53:00–01:53:30).
- C17 all-UAV-death at 06:56:30 is **battery exhaustion**: every UAV last-alive with
  `battery_pct = 0.04 %` and `is_at_usv = False` (not RTB/landed) → engine `uavbattery` kills it.
- C17 clamp **is bypassed by `_search_fly`** (returns an action directly, not via `_fly`); UAVs reached
  max |y| = 236 km. VERIFIED.
- E19's route reconstruction is **approximate (INFERRED)**; the 57.3 km figure is corroborated by the
  real detected 60 s window, not claimed as per-second truth.
