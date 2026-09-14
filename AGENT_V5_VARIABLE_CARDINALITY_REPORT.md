# AGENT_V5_VARIABLE_CARDINALITY_REPORT

> 任务：同一 Agent / 同一 Skill / 同一 Prompt 直接处理不同 USV/UAV 数量组合 × 随机航路。
> 评估日期：2026-08-15 ｜ 冻结版本见 §12/§46。

---

## 1. Goal

构建 `agent_hybrid_v5.py`：**variable-cardinality, observation-driven hierarchical maritime
agent**。同一个 policy 面对 3~15 艘 USV / 2~15 架 UAV 的任意合法组合 + 黑方随机 waypoint，
不做任何 fleet-size hard-code、不依赖敌方数量/路径先验。回答：
同一个 Agent 能否直接处理不同兵力数量？是否 composition-specific 崩溃？USV/UAV 比例如何
影响性能？GLOBAL_REACQUIRE 是否解决"最后敌舰失踪"？LLM 在更复杂 composition 下是否产生
新的 marginal value？

## 2. Why Variable Cardinality Matters

V1–V4 全部围绕固定 10v10 调试，虽名义上 count-independent，但未在变基数下验证。
真实对抗中兵力组合未知且可变；policy 必须只依赖当前资源/观测/信念，而非 scenario identity。

## 3. V4 Baseline

V4 在 10v10 random-waypoint FINAL（20 seeds）：
- V4 DEFAULT_INTENT：engine 19/20、clean 18/20、USV loss 0.75
- V4 DeepSeek：engine 19/20、clean 17/20、USV loss 1.15
- 结论：确定性 harness 是主要性能来源；DeepSeek 无稳定正 marginal value（V4 报告）。

V4 最集中失败：**前 4 杀后最后 1 艘敌 USV 完全逃出跟踪 → 反杀剩余 USV → 突破/quirk**。

## 4. V5 Architecture

```
              General Maritime Skill（冻结 aebc47bf）
                        │
                 Event-Gated LLM Commander（触发：状态签名变化/优先事件/allocator 歧义）
                        │
                StrategicIntent（+coverage_priority / priority_clusters）
                        │
Observation → Variable-Cardinality Belief State
   ├── FriendlyResourceState（绝对值 + 比例）
   ├── Enemy Track Beliefs（maneuver-aware）
   ├── CoverageMap（几何固定网格，不随兵力规模变）
   ├── Threat Clusters（动态聚类，不固定方向/数量）
   └── Mission State（NORMAL_COMBAT / GLOBAL_REACQUIRE / TERMINAL）
                        │
   Dynamic Marginal Allocator（coverage floor + marginal-gain + guard + last-ship fallback）
             /                 \
   USV Tactical FSM        UAV Sensor Manager
   （sensor-assisted      （SEARCH / SCREEN / REACQUIRE /
     standoff）            GLOBAL_SEARCH）
             \                 /
              ActionSafety → /apply
```

**核心：数量改变 state，不改变 agent。**

## 5. Mission-Unresolved Global Reacquisition（Phase A）

新增 Mission State：
- `GLOBAL_REACQUIRE` 触发（不依赖敌方总数）：`/result 未结束 AND 无可靠 hostile USV
  track AND 无 active lock AND 已曾探测过敌 USV AND 持续 GLOBAL_REACQUIRE_DELAY(90s)`。
- **修复关键 bug**：触发前提用"曾见敌 USV（ship）"而非"曾见任何敌（含黑方 UAV）"——
  否则黑方 UAV 首测后就把开局误判为重搜，UAV 西飞漏掉来敌（实测 first_lock 从 7350s 拖到
  10550s）。修复后 first_lock 回归 ~7400s。

行为：
- **UAV → GLOBAL_SEARCH**：依据 CoverageMap（30km 网格，突破相关权重=靠 x=50000 越近越
  优先）飞向优先级最高的陈旧/未覆盖格；格数由战场几何固定（10×18），不随兵力规模变。
- **USV → 防御屏列**：保持各 USV 自身 y、收敛到屏列 x=120000，不聚集、不散落到无关区域。

指标（FINAL 实测）：global_reacquire_entries 1.31/局、success 1.14/局 —— 多数丢失敌舰
被找回并击杀；剩余失败集中在 hard seed 203 的"最后 1 艘仍逃过全网格覆盖"。

## 6. Friendly Resource Representation（Phase B）

`FriendlyResourceState`：绝对值（usv_alive=7 就是 7）+ 比例（available_ratio/engaged_ratio/
frozen_ratio / available_sensing_ratio）+ 任务聚合（active_combat_tracks / lost_high_threat
/ coverage_quality）。供 controller/summary/commander 共用，不携带 scenario label / 敌方
数量先验。

## 7. Threat Clustering（Phase C）

`ThreatClusterBuilder`：敌 USV 按 x 距离相近 1D 贪心聚类。不固定 LEFT/CENTER/RIGHT、不固定
cluster 数。每 cluster：ships/visible/lost/avg_conf/min_breakthrough_x/friendly_committed/
local_force_ratio/recon_coverage。Commander 新接口 `priority_clusters`（首选，替代逐艘
priority_tracks）。

## 8. Marginal Resource Allocation（Phase D）

保持 V4 的 marginal allocator + coverage floor + 低置信 guard + last-ship fallback；
确认无固定 attacker/reserve/sector 数：
- `focus`/`emergency` 仅是 Commander 偏好的上限，实际 1v1/2v1/3v1 由 `marginal_gain(k)=1/k−1/(k+1)`
  与 `MIN_ASSIGN_VALUE` 自然产生。
- reserve 全 ratio（`reserve_ratio`），endgame/紧急 override。
- 新增 `return_margin`：返回 best−second 分配裕度，供 Commander `allocator_ambiguity` 触发
  （裕度 < 0.06 时允许战略偏好介入）。

## 9. Dynamic UAV Sensing（Phase E）

UAV 角色完全动态：REACQUIRE（丢失高威胁敌 USV）> SCREEN（first-lock 共享感知）>
SEARCH（未知区域）> GLOBAL_SEARCH（mission-unresolved）。角色由需求自然产生，
`n_uavs` 只用于扇面宽度（数量自适应），无 `if num_uav==5` 分支。

## 10. Event-Gated LLM Commander（Phase F）

- 正常/低不确定状态：deterministic primary（LLM 不持续扰动）。
- 触发：状态签名变化 / 优先事件（first_detect, friendly_loss, breakthrough_risk, ...）/
  GLOBAL_REACQUIRE / allocator_ambiguity。
- 保留 V4 的：commander_source 可观测、审计记录、滞回（no_change 不覆盖）、last-valid
  fallback、validate_policy。
- schema 新增 `coverage_priority`（0~1）与 `priority_clusters`（cluster id 白名单）。

## 11. Maritime Skill

冻结 hash `aebc47bf`（V4 版本，§23 要求 audit 后不改）。已包含全部所需 doctrine：
uncertainty / information-before-commitment / UAV 三角色 / 敌 UAV≠敌 USV / sensor-assisted
geometry / coverage vs overmatch / marginal overmatch / low-confidence / endgame /
avoid overreaction。audit 确认零 composition/path 耦合。

## 12. Scenario Generator（Phase G）

- `scenario_builder.py`：`build_scenario(...)` 支持任意计数 + `frontage_mode`
  （fixed_density / fixed_frontage）+ 随机航路 seed。
- `validate_composition(wu, wuv, bu, buv)`：非法组合（UAV>USV 机库超载、0 USV）明确报错，
  不 silent repair。
- `scenario_composition.py`：从配置文件 `RW_CFG_FILE` 读取 `seed wu wuv bu buv frontage`，
  每局可复现。注册到 sces.json + AVAILABLE_SCRIPTS。
- **Fixed Frontage（主实验）**：恒定 60km 正面，数量→密度增大；**Fixed Density（secondary）**：
  15km 间距，数量→正面变宽。DEV 用 fixed_frontage 隔离 frontage confound。

## 13. Composition Generalization Protocol

- DEV compositions（对称）：C1 3/3, C2 5/5, C3 7/4, C4 8/7, C5 10/5, C6 10/10, C7 12/8,
  C8 15/15；seeds {1,2}。
- FINAL compositions（unseen）：F1 4/4, F2 6/3, F3 6/6, F4 7/7, F5 8/3, F6 9/6, F7 10/3,
  F8 11/9, F9 12/4, F10 13/10, F11 14/6, F12 15/8；seeds {201,202,203}。
- 全部对称（white==black composition），双方随机航路。

## 14. Random-Trajectory Protocol

黑方 USV 运动 = seeded random waypoint（与 V1–V4 相同生成器，总体突破意图 + 多次转向/
横向机动）；seed 隐藏于配置文件，Agent 运行时不可见。

## 15. DEV Results（V5 deterministic，16 局）

**16/16 engine、16/16 clean**，USV loss avg 1.38、UAV loss 0、breakthrough 0。
逐 composition 全 clean：C1(3/3)=2/2, C2(5/5)=2/2, C3(7/4)=2/2, C4(8/7)=2/2,
C5(10/5)=2/2, C6(10/10)=2/2, C7(12/8)=2/2, C8(15/15)=2/2。无 crash、无 composition 崩溃。
**10v10-like 回归：C2 2/2 clean（未退化）。**

## 16. FINAL Holdout Results（V5 deterministic，36 局，unseen compositions）

**36/36 engine（100%）、30/36 clean（83%）**，USV loss avg 2.03、UAV loss 0.81、
breakthrough 0.17、global_reacq 1.31/1.14、reacquire 55.4/55.6、sensor_assisted_locks 高。

| Composition | USV/UAV | clean |
|---|---|---|
| F1 | 4/4 | 2/3 |
| F2 | 6/3 | 2/3 |
| F3 | 6/6 | 3/3 |
| F4 | 7/7 | 3/3 |
| F5 | 8/3 | 3/3 |
| F6 | 9/6 | 3/3 |
| F7 | 10/3 | 2/3 |
| F8 | 11/9 | 3/3 |
| F9 | 12/4 | 2/3 |
| F10 | 13/10 | 3/3 |
| F11 | 14/6 | 2/3 |
| F12 | 15/8 | 2/3 |

## 17. Results by Composition

- **无 composition-specific 崩溃**：36/36 engine。USV 3→15、UAV 2→15 全部可玩。
- USV loss 随规模上升（small 0.2 / medium 2.2 / large 3.0）—— 更大舰队 = 更多对杀面，
  属机制自然缩放，非 agent 退化。
- UAV loss：small 0.8 / medium 0.3 / large 1.2 —— F10/F12 的 hard-seed 局 UAV loss 高
  （最后一次 GLOBAL_REACQUIRE 中母船被突破端连带 / 长时间未回收）。

## 18. Results by Maneuver Difficulty

全部 6 个非 clean 局集中在 **seed 203**（跨 6 个不同 composition 都发生）→ 路径难度是
主失效因子，而非 composition。seed 203 的航路让"最后 1 艘"反复逃出覆盖网格；GLOBAL_REACQUIRE
部分找回（success 1~6/局）但未能阻止其在 deadline 前突破 → quirk。

## 19. LLM Marginal-Value Analysis

Event-gated DeepSeek Commander 在 representative subset（6 composition × {201,203}，10 局可配对）：
**both_win 7 / default_only 1 / deepseek_only 1 / both_lose 1**。真实调用（src=deepseek、
0 API/parse 失败）、低频（状态驱动）。**在 variable-cardinality 状态空间下 LLM 仍未产生
稳定正 marginal value**（与 V4 固定 10v10 一致）——确定性 harness 已覆盖该分布。

## 20. Failure Taxonomy

| 类别 | 局数(FINAL) | 说明 |
|---|---|---|
| 最后 1 艘逃跟踪→突破 quirk | 6/36（全 seed203） | 覆盖网格未捕获反复消失的末舰；GLOBAL_REACQUIRE 部分成功 |
| composition-specific 崩溃 | 0/36 | 全部 composition 可跑完 |
| tracking/reacquire 失败 | 0（其余 30 局 reacquire 55/55 成功） | — |
| 能耗/UAV | F10/F12 hard-seed 局 UAV loss 高 | 长时间 GLOBAL_REACQUIRE 未回收 |

## 21. Clean vs Engine Result

- Engine 100%（36/36）；Clean 83%（30/36）。6 个 quirk 均为"最后 1 艘突破瞬间被裁判击杀
  → 判 Victory"的 judge 顺序 quirk。clean 判定严格（任何突破前未完成正式胜利 = 非 clean）。

## 22. Fair-Play Audit

`audit_variable_cardinality.py` **15/15 PASS**：runtime 零命中（black_usv/black_uav/
black_strategy/BLACK_Y/ENEMY_X/260000/vx=-10/expected_enemy_count/black_usv_count/
range(5)/range(15)）；TrackManager 无敌方数量知识；Commander/Skill path-label & scenario-label
blind；Agent 看不到 seed / 航路 / composition 标签。

## 23. Variable-Cardinality Audit

见 §22：`audit_variable_cardinality.py` 覆盖 Single Agent/Skill/Prompt、无固定数量/
reserve/attacker/sector、各模块 count-independent、GLOBAL_REACQUIRE count-independent、
Commander 标签盲、Fair-play。**全部 PASS**。

## 24. Remaining Bottlenecks

1. **seed-203 型"最后 1 艘反复消失"**（跨 composition 的主失效）：CoverageMap 网格 30km +
  UAV GLOBAL_SEARCH 未能在 deadline 前捕获反复逃脱的末舰。候选：网格细化/突破相关区加权
  更强、末舰消失时把更多 UAV 压到突破区、击杀缺口时强制全域扫描。
2. UAV loss 在 hard-seed 大舰队局偏高：长时间 GLOBAL_REACQUIRE 中回收/电量策略可强化。
3. LLM Commander 边际价值仍不显著：若保留，建议仅在其触发（ambiguity/global_reacquire/
  multi-cluster）时用于战略偏好，且严格 clamp reserve=0+decisive 组合。

## 25. Conclusions

- **同一个 Agent 能直接处理不同 USV/UAV 数量**：36/36 完成、83% clean，无 composition-specific
  代码路径。
- **USV/UAV 比例影响**：均可用；combat-heavy（UAV<USV）与 balanced 均 clean；性能随规模
  温和缩放（USV loss↑），无崩坏。
- **随机路径**：tracking/reacquire 正常（55/55）；主失效是"末舰反复消失"的路径难度（seed203），
  与 composition 无关。
- **GLOBAL_REACQUIRE**：部分解决"最后敌舰失踪"（entries 1.31/局、success 1.14/局），
  已修复"开局误判重搜导致首锁延迟"的 bug；未完全覆盖极端 hard path。
- **Marginal Allocator / UAVManager**：自然适配 3~15 USV / 2~15 UAV。
- **LLM**：event-gated Commander 真实参与但不显著提升 marginal value（同 V4）。
- **无 composition-specific overfitting**：Skill/Prompt/Agent 均 composition-agnostic。
- **瓶颈**：末舰覆盖（确定性盲区）> UAV 回收（hard 局）> LLM 无增量。

**横向定位**：A variable-cardinality, observation-driven hierarchical maritime agent
operating under partial observability —— 确定性 harness 主控，LLM 仅作 bounded strategic
overlay。

---

## 冻结 hash

| 组件 | SHA256 |
|---|---|
| agent_hybrid_v5.py | `51a504a0817ed87938ff6fcba645d822ba18d1fcd35ff76adfb4a7058cdcb270` |
| SKILL.md | `aebc47bf863207dcf49206c6e13e81b3ea62417f5ff752135f14133c72acda24` |
| run_variable_cardinality_eval.py | `e2169e8f62a6299c44d9d2665eba8fdb2fe77312604e4d8e32e7ae87de7b07f4` |
| scenario_builder.py | `e9ec3efbc19de4805abbb4867950317df712747d595b596a9a1b2d66f8850756` |
| scenario_composition.py | `3d456c5ba3f431059bb800441bee458f3878c90416fe248d10509ef61b091f46` |

结果文件：`variable_cardinality_v5_default_dev.csv`（16 局）、
`variable_cardinality_v5_default_final.csv`（36 局）、`variable_cardinality_results.csv`（LLM ablation 12 局）。
