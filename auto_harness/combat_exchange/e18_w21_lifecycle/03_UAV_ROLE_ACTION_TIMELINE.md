# 03 — UAV ROLE / ACTION TIMELINE
- `UAV_TRACE` (E12) shows roles/actions; the W2-1 deaths are **sequential** (not one mass step), and every
  UAV's last-alive position is at the **northern area edge** (y≈276–277 km), while surviving C17 UAVs stay
  at |y|≤95 km. The dominant exit is therefore **area-out** (judge `_judge` area loop: units outside
  `self.area` are killed), not battery (`total_fly_time=25000 s`; deaths at ~9.6–11.8 ks) and not combat
  (White USVs don't die until ~27 ks).
- No RETURN/LANDING/failure event corresponds to these deaths.
