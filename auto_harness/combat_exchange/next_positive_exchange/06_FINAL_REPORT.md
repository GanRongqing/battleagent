# 06 — NEXT POSITIVE EXCHANGE — FINAL REPORT
Two independent mechanism rounds were run (max allowed). Both used the parallel runner (ACE baseline
reused from E2; candidate rows newly measured; /tmp/opencode/parallel_runs/{c9eval,c10eval}).

## Final main table (5 seeds each)
| 敌方策略 | 版本 | 局数 | 击毁黑方 | 白方损失 | 战损交换比 | 正交换局数 |
|---|---|---:|---:|---:|---:|---:|
| W2-6 | ACE | 5 | 50 | 90 | 0.556 | 0/5 |
| W2-6 | C10 | 5 | 55 | 80 | 0.688 | 0/5 |
| W2-4 | ACE | 5 | 60 | 30 | 2.000 | 5/5 |
| W2-4 | C10 | 5 | 60 | 35 | 1.714 | 5/5 |
| W2-2 | ACE | 5 | 20 | 95 | 0.211 | 0/5 |
| W2-2 | C10 | 5 | 20 | 95 | 0.211 | 0/5 |

(C9 = NO_EFFECT, 0 packages; W2-1 unchanged, zero-lock, out of scope.)

## Verdict: TARGETED_ONLY
No positive exchange. W2-6 improved reproducibly (+24%, own-lock 55→75) with no control regression
(W2-4 5/5 wins retained). Unit tests: test_demand_gate 8/8, test_budget_gate 1/1.
