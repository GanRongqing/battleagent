# 02 — W2-2 CONTROL (ACE + E7 winning config, seed 43001)
- Result: **0 kills / 20 losses / CER 0.000** (baseline ACE: 4/19 = 0.211).
- Trajectory hash `166f0d333829`; valid, no runtime errors.
- vs baseline: kills 4->0, losses 19->20 → **W2-2 REGRESSION** (the fix does not help, and removes the
  small baseline kill count).
- Caveat: this trajectory is **byte-identical** to the W2-1 run (same white positions, empty
  active_enemies at 300/600/800) → scenario separation not independently proven for this pair;
  treat the W2-2 number as indicative, not a clean control.
