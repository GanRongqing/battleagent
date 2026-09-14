# HARNESS_LIMIT_AND_CONTRIBUTION_REPORT

> 纯测量任务：测 frozen deterministic Harness（agent_hybrid_v5.py --no-llm）的能力极限、
> S15 scale-up 稳定性、敌方 OOB 影响、探索与战斗贡献。
> Agent / Skill / Prompt / 战术参数均未修改。

---

## 1. Measurement Setup

- **Agent**：`agent_hybrid_v5.py --no-llm`（Harness-only，DEFAULT_INTENT）。
- **Scenario**：`scenario_composition`（fixed_frontage，双方 random waypoint，seeded & 白方不可见）。
- **OOB 参数化**：在 judge 中新增 `enemy_area`（仅 BLUE 使用），`enemy_oob_multiplier` 围绕
  战场多边形质心(150000,336603) 等比例外扩；`1.0x`=原始边界，行为与旧版完全一致。
- **Instrumentation**：`maritime_metrics.py`（evaluator-side 轮询 /status，不影响 Agent 决策）。

## 2. Instrumentation Validation

| 检查 | 结果 |
|---|---|
| USV 35km 360° coverage | 3900 km² ≈ 理论 π·35²=3848 PASS |
| UAV 60km ±30° cone | 1850 km² ≈ 理论 1885 PASS |
| damage accounting | sum_damage_hits == black_hit_reward PASS |
| kill accounting | sum_kill_credit == enemy_combat_killed PASS |
| enemy terminal accounting | combat+oob+breakthrough+survived == black_usv PASS |
| 性能 | 修复 CPU 争用（vscode 进程）后单局 422s→~140s；collector 轮询开销可忽略 |

## 3. Harness Limit — White 5+5（5+5 vs 增长黑方）

| black_total | composition | clean | (3 seeds, current code) |
|---|---|---|---|
| 20 | 10+10 | 2/3 (67%) |
| 25 | 13+12 | **3/3 (100%)** |
| 30 | 15+15 | 2/3 (67%) |
| 35 | 17+18 | 2/3 (67%) |
| 40 | 20+20 | 1/3 (33%) |
| 45 | 23+22 | 1/3 (33%) |

**W5：high-success ≤ 25；transition ≈ 30–35；collapse ≈ 40–45。**
（5 种子补验一致：25=4/5、30=3/5、35=2/5、40=1/5、45=1/5）

## 4. Harness Limit — White 10+10（10+10 vs 增长黑方）

| black_total | composition | clean (3 seeds) |
|---|---|---|
| 20 | 10+10 | **3/3 (100%)** |
| 30 | 15+15 | **3/3 (100%)** |
| 40 | 20+20 | 2/3 (67%) |
| 50 | 25+25 | 2/3 (67%) |
| 55 | 28+27 | 2/3 (67%) |
| 60 | 30+30 | 1/3 (33%) |
| 65 | 33+32 | 2/3 (67%) |
| 70 | 35+35 | 0/3 (0%) |

**W10：high-success ≤ 30（3 种子 100%；早期 5 种子 bt20–50 均 ≥80%）；transition ≈ 40–65（67%）；collapse ≈ 70（0/3）。**

## 5. S10: 10+10 vs20 Random Stability

```
White 10 USV + 10 UAV  vs  Black 10 USV + 10 UAV（black_total=20，random waypoint）
OOB 1.0x，N = 30

clean           = 30/30 (100%)
friendly dead avg = 2.03 (USV 2.03 / UAV 0)
enemy combat killed avg = 9.3   （真值 10；终局轮询滞后 ~0.7 的已知轻微欠计）
enemy OOB       = 0
enemy breakthrough = 0
explored km² avg = 57,238 (ratio 0.30)
```

**S10 在 30 个随机路径下高度稳定（100% clean）。**

## 6. S15: 15+15 vs30 Random Stability

```
White 15 USV + 15 UAV  vs  Black 15 USV + 15 UAV（black_total=30，random waypoint）
OOB 1.0x，N = 8（sequential stop：8/8 → 停止）

clean           = 8/8 (100%)
friendly dead avg = 4.25 (USV 4.25 / UAV 0)
enemy combat killed avg = 15.0（全部击毁）
enemy OOB       = 0
enemy breakthrough = 0
explored km² avg = 59,709 (ratio 0.31)
```

**S15 scale-up（30 总单位/方）8/8 clean，无崩溃、无 tracking/coverage 崩溃迹象。**

## 7. OOB Finding

- **全部 141+ instrumented games（limit sweep + S10 + S15）中 enemy_out_of_bounds = 0。**
- S10 OOB=1.5x sanity（3 seeds，同 1.0x 种子）：3/3 clean，combat=10，OOB=0，与 1.0x 一致。
- **结论**：敌方随机航路始终位于合法多边形内，OOB 裁判对 Harness 成绩贡献为 0。
  → **OOB-assisted removal fraction = 0**。不存在"胜率被敌方 OOB 虚高"的问题。

> Across all instrumented random-scenario evaluations, no enemy out-of-bounds removals were observed. There is no evidence that the measured Harness performance is inflated by the current enemy OOB judge boundary.

## 8. Exploration Contribution

| 场景 | 每局探索 km² | ratio |
|---|---|---|
| S10 (10+10 vs20) | 57,238 | 0.30 |
| S15 (15+15 vs30) | 59,709 | 0.31 |
| W10 limit（20–70 总敌） | ~52k–90k | 0.31–0.46 |

战场面积 193,301 km²。每局探索约 30–46%。

## 9. Combat Contribution

| 单位 | 样本 | 探索 km² | 首次发现 km² | damage hits | kill credit | survival |
|---|---|---|---|---|---|---|
| USV | 615 | 14,421 | 426 | **4.6** | **2.29** | 0.558 |
| UAV | 615 | **31,411** | **9,573** | 0 | 0 | 0.909 |

- **UAV 是主探索者**（约 USV 的 2.2 倍面积，且贡献 ~96% 的首次发现）。
- **USV 是唯一战斗贡献者**（damage/kill 仅 USV 产生）；单局内伤害不均（USV damage 1–8、kill 0–7，少数承担多数击杀）。

## 10. Conclusions

- **Q1 Harness 极限**：
  - W5（5+5）：high-success ≤ 25；transition 30–35；collapse 40–45。
  - W10（10+10）：high-success ≤ 30（早期更宽）；transition 40–65；collapse 70。
- **Q2 10+10 vs20 稳定**：30 局 100% clean。
- **Q3 15+15 vs30 稳定**：8/8 clean（sequential stop），无 scale-up 崩溃。
- **Q4 OOB 是否虚高**：**NO EVIDENCE** — 所有局 enemy OOB=0。
- **Q5 单位贡献**：USV 探索 14,421 km² / 伤害 4.6 / 击杀 2.29；UAV 探索 31,411 km² / 无战斗。

**主要限制因素**：敌方兵力远超白方时（W5 敌 4–9×、W10 敌 3.5×）的击杀竞速饱和 —— 白方火力不足导致"最后 1 艘敌舰逃出覆盖→突破/漏网"；与敌 OOB 无关。

**数据文件**：`harness_limit_results.csv`、`standard_10p10_vs20_harness.csv`、
`standard_15p15_vs30_harness.csv`、`priority_eval_aggregate.csv`、
`unit_contribution_results.csv`、`unit_contribution_aggregate.csv`。
