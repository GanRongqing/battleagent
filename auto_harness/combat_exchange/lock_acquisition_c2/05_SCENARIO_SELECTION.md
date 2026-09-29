# 05 — Diagnostic Scenario Selection

Per-strategy no-lock rate (baseline W5, 24 episodes, per-assignment):

| strategy | assignments | no-lock | no-lock rate | LA-F1 | LA-F6/3 |
|---|---|---|---|---|---|
| S1 横向中央汇聚 | 690 | 166 | 24% | 95 | 71 |
| S2 扇形展开 | 182 | 40 | 22% | 28 | 11 |
| S3 两翼包抄 | 231 | 50 | 22% | 38 | 12 |
| S4 南北镜像 | 92 | 34 | 37% | 23 | 10 |
| S5 菱形中央汇聚 | 32 | 24 | **75%** | 20 | 2 |
| S6 MUSV绕行 | 168 | 82 | **49%** | 76 | 4 |

Selected (maximum information for LA-F1 = never-closed):
- **Hard / primary = S1** (largest absolute no-lock 166 and LA-F1 95; enough assignments for a
  meaningful per-assignment lock-conversion comparison in one episode).
- **Control / secondary = S6** (49% no-lock rate, LA-F1 76) — the strongest *rate* stress case with enough
  assignments.

(S5 has the highest rate 75% but only 32 assignments -> too few for a stable within-episode comparison.)

Seeds: fresh **12301** (does not reuse DEV seeds 12101/12102). Comparison is ACE vs C2 on the same seed.
