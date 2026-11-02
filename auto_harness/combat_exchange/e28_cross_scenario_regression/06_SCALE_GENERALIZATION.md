# 06 — SCALE GENERALIZATION
| scale (W/B USV+UAV) | C10 K/L (CER) | C30 K/L (CER) | verdict |
|---|---|---|---|
| 5+5 / 5+5 (S10) | 5/1 (5.00) | **0/5 (0.00)** | MAJOR regression (C30 wipes, 0 kills) |
| 5+5 RW (S10RW) | 5/0 (INF) | **0/5 (0.00)** | MAJOR regression |
| 8+7 / 8+7 (S15) | 8/0 (INF) | 8/7 (1.14) | same kills, +7 losses |
| 10+10 / 10+10 (S20) | 10/1 (10.0) | 10/8 (1.25) | same kills, +7 losses |
| 15+15 / 15+15 (S30) | 15/0 (INF) | 15/10 (1.50) | same kills, +10 losses |
C30 kills parity at ≥8v8 but suffers far more USV losses; at 5v5 it collapses (0 kills, all USVs lost).
=> `SCREEN_EVERY=3` + unconditional press is **not scale-robust**: at small N the split fragments the force;
at larger N the press over-commits. (VERIFIED for the tested set; mechanism INFERRED from K/L + config.)
