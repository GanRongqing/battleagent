# AGENT_V4_DEEPSEEK_COMMANDER_REPORT

> 任务：10v10 random-waypoint 下，检验"真实 DeepSeek 战略 Commander"是否能在不削弱
> 强确定性 V3/V4 harness 的前提下提供可测量的边际价值。
> 评估日期：2026-08-14 ｜ 冻结版本（FINAL_TEST 后未再改动）

---

## 0. 冻结版本

| 组件 | SHA256 |
|---|---|
| agent_hybrid_v4.py | `37cdba68bbf659edd81fed9e2d5deda43ebc45697b5c774ea5a0781ea1bed663` |
| skills/maritime_commander/SKILL.md | `aebc47bf863207dcf49206c6e13e81b3ea62417f5ff752135f14133c72acda24` |
| run_random_waypoint_eval.py | `6213c8a83f3b4ec1d8e29c449ad7b39456cd986df0006eaa90049820d120b7c7` |
| FINAL_TEST seeds | 201–220（20 个全新随机航路种子，开发期未查看） |
| scenario | `scenario_10v10_rw`（5 USV + 5 UAV，只改黑方 USV 运动路径） |

V3 hash（历史基线）：`ad5df83d2cf092eec02d0a86af5fb92caf15ca8c1557329292f04030411560d4`
V4 由 V3 增量复制（确定性层 100% 保留），仅 Commander 层升级 + 战略字段接入确定性控制器。

---

## 1. V3 architecture baseline

V3 确定性层（全部保留到 V4，无改动）：

```
Observation(/status + /legal_actions)
  → TrackManager（maneuver-aware belief：heading/turn/maneuver_score/point_confidence/
                  uncertainty_radius/predicted_region；敌 USV 300s 保留）
  → ThreatAllocator（marginal-value：kill_time≈750/k s → marginal_gain=1/k−1/(k+1)；
                     coverage floor；低置信 commit guard；last-ship fallback）
  → USVController（sensor-assisted first-lock；~34km in-radar standoff band）
  → UAVManager（SEARCH/SCREEN/REACQUIRE 动态角色；region sweep reacquire；SAFE_LOITER）
  → ActionSafety（全动作 /legal_actions 双重校验）
  → /apply
```

V3 关键结果（此前评估）：DEV 9/10 clean；FINAL holdout（旧 101–120）18/20 clean、
USV loss 0.65。V3 结果是在 LLM 环境变量缺失时以 `DEFAULT_INTENT` 兜底跑出的。

## 2. real Commander wiring

- DeepSeek key 从本机 `~/.cline/data/secrets.json` 读取（`deepSeekApiKey`），经
  `ANTHROPIC_AUTH_TOKEN` 注入；`ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic`，
  模型 `deepseek-v4-flash`，`thinking: disabled`。
- 真实链路验证：HTTP 200 + 单局 smoke 17 次 `COMMANDER RESPONSE`、0 fallback；
  FINAL_TEST 全程 `commander_source=deepseek`、`commander_api_failures=0`。
- 延迟：~2.0–2.3s（实况）≈ 100–115 仿真秒；无阻塞（后台线程 + 锁 + 快照摘要）。

## 3. Commander observability

- `commander_source`：`deepseek / provider_fallback / parse_fallback / default_intent`，
  每局记录进 `[META]` 与 CSV（严格区分"真 Commander"与"兜底"）。
- 结构化审计 `commander.audit[]`：`{sim_time, trigger, source, parse_success,
  policy_success, fallback_reason, intent.describe(), latency}`；局终写
  `commander_audit_seed.json`。不含密钥/思维链。
- 计数：`calls / responses / no_change / parse_failures / api_failures /
  policy_failures / latency_sum`。

FINAL_TEST 实测（n=20）：calls/game 12.15、changes/game 10.8、no_change 1.35、
api_failures 0.0、policy_failures 0.05、avg latency 5.23s（含个别慢响应）。

## 4. V4 architecture

V4 = V3 确定性层 + 升级的 Commander 层：

1. **状态驱动触发 + 滞回**：`_state_signature()`（USV 存活/敌舰数/lost/engaged/
   uncovered/突破档/平均点置信/不确定数）签名变化才触发；优先事件（first_detect/
   friendly_loss/breakthrough_risk/multi_frozen/threat_spike/lost_high_threat）仍即时触发；
   最小间隔 600s + in_flight 保护；新 intent 战略字段与当前相同（`__eq__`，不含 reason）
   → 计 `no_change` 不覆盖（防振荡）。
2. **战略政策校验** `validate_policy(ctx)`：
   - 全接触不确定（blind）→ recon_aggressiveness ≥ 0.5（不饿死侦察）
   - 突破临近 → reserve_ratio ≤ 0.10、engagement_aggressiveness ≥ 0.5
   - 寡不敌众（USV<敌舰）且 decisive → focus_level ≤ 2
   - 其余安全不变量仍由确定性层强制，prose 不承担约束。
3. **战略字段全部接入确定性控制器**（此前仅 standoff 生效）：
   - `overmatch_policy` → allocator `MIN_ASSIGN_VALUE` 缩放（economical 1.6×/balanced 1.0×/decisive 0.6×）
   - `uncertainty_tolerance` → 低置信 guard 阈值 `clamp(0.55−tol, 0.15, 0.60)`
   - `recon_mode` → UAV screen 门槛（screen_priority 0.25 / balanced 0.45 /
     reacquire_priority 0.55 / broad_search 0.75）
   - `standoff_preference` → USV band（low 31.5km / medium 34km / high 35.5km）
4. **Commander 审计持久化**（见 §3）。

## 5. StrategicIntent interface

保留 V3 的 compact schema：

```json
{ posture, focus_level, emergency_focus_level, reserve_ratio, reserve_usvs,
  threat_bias, priority_tracks, uav_mode, uav_priority_tracks,
  recon_aggressiveness, engagement_aggressiveness,
  overmatch_policy, recon_mode, standoff_preference, uncertainty_tolerance, reason }
```

FINAL_TEST 实测意图多样性（模型真实使用）：focus {2,3}、reserve_ratio {0..0.35}、
overmatch {economical, balanced, decisive}、recon_mode {broad_search, balanced,
screen_priority, reacquire_priority}、unc_tol {0.2..0.6}。Commander 有真实杠杆。

## 6. Commander trigger policy

- 低频（FINAL_TEST 平均 12.15 次/局，对比战术步 ~350–500 次/局）。
- 状态签名驱动：同签名 + 非优先事件 → 不调用（防每 tick 空转）。
- 单测验证：同签名 periodic 不触发、异签名触发、优先事件无视签名触发。

## 7. safety / fallback logic

- 兜底链：last valid intent → DEFAULT_INTENT（LLM 失败/畸形/超时都不崩溃）。
- 解析：括号平衡 JSON 提取，容忍 markdown 围栏；白名单 clamp（posture/bias/uav_mode/
  overmatch/recon_mode/standoff/数值）。
- 政策校验在 schema 之后做 doctrine clamp；全部安全不变量在确定性层硬编码。
- LLM_ENABLED=false → 无调用、source=default_intent、行为=V3 确定性（单测覆盖）。

## 8. Tactical Summary changes

摘要新增/强化（保持 top-K 压缩，规模无关）：
- MANEUVER：`high_maneuver_tracks / high_uncertainty_tracks / avg_point_conf`
- ENGAGEMENT：`first_lock_candidates / targets_engaged / targets_unassigned`
- RECON：`reacquire_demand / screen_demand / search_needed / uav_airborne`
- FORCE：`usv_alive / available_ratio / engaged_ratio`
- THREAT CLUSTERS：确定性轻量聚类（ship-only，按 x 相近分组，含 committed/近突破）

## 9. SKILL.md changes

新 hash `aebc47bf`。重写为面向 DeepSeek 的 doctrine（全部 path/scale-agnostic）：
Mission 五级优先级 / Fair-play / Uncertainty semantics（分级不二值）/ UAV 三角色 /
敌 UAV≠敌 USV / USV 几何（sensor-assisted，不写死距离）/ coverage vs overmatch /
marginal overmatch / 低置信提交 / maneuver detection / endgame（最后 1 艘绝不无人覆盖）/
avoid overreaction / Commander role（模型建议、harness 约束）。
零命中：10v10/15v15/random waypoint/seed/waypoint/black_* /260000（fair-play 审计通过）。

## 10. doctrine changes

四条核心 doctrine 保留并强化（Maneuver Uncertainty / Information Before Commitment /
Sensor-Assisted Engagement / Marginal Local Overmatch），并补充端局与防过反应边界。

## 11. unit tests

- `test_v3_units.py`：49/49（V3 确定性层）
- `test_v4_units.py`：41/41（fake Commander，无真实 provider）覆盖：
  source accounting、policy validation、last-valid fallback、DEFAULT fallback、
  状态驱动触发（防 spam）、滞回 no_change、intent persistence、invalid rejection、
  allocator wiring（overmatch/unc_tol）、敌 UAV 非舰、coverage floor、SAFE_LOITER、
  path-agnostic prompt、runtime fair-play zero-hit。

## 12. DEV setup

10 个 DEV seeds（1–10），与 V3 相同的随机航路生成；三种变体配对同 seed：
- V3 DEFAULT_INTENT（历史，LLM 缺失时兜底）
- V4 DEFAULT_INTENT（`--no-llm`）
- V4 DeepSeek Commander（真实模型）

## 13. V3 DEFAULT_INTENT baseline（DEV）

V3 确定性：10/10 engine、9/10 clean、USV loss 1.2、UAV loss 0。

## 14. real DeepSeek baseline（DEV）

V4 真实 DeepSeek：10/10 engine、**7/10 clean**、USV loss 1.6、UAV loss 0.1；
`commander_source=deepseek`（0 provider/parse failure）。3 个 quirk（seed 4/5/7，
最后 1 艘漏网→突破→judge quirk）。

## 15. architecture ablation（DEV）

| Variant | Engine | Clean | USV loss |
|---|---|---|---|
| V3 DEFAULT | 10/10 | 9/10 | 1.2 |
| **V4 DEFAULT** | 10/10 | **10/10** | 1.0 |
| **V4 DeepSeek** | 10/10 | 7/10 | 1.6 |

确定性架构增益（V3→V4，仅战略字段接入 + 触发/校验/观测）：DEV 9→10 clean、
USV loss 1.2→1.0（小样本内）；Commander 边际价值在 DEV 上为**负**（7 vs 10 clean）。

## 16. skill ablation

未单独跑（实现成本/样本限制）。SKILL 质量由真实 DeepSeek 输出质量与最终结果间接体现
（§19 分析）。若优先考虑隔离，下一步可做 "DeepSeek + 旧 skill" 对比。

## 17. FINAL_TEST setup

20 个全新 seeds（201–220），生成逻辑与 DEV 相同（seed → RNG → 黑 USV 随机航路），
已验证确定性 & 边界内；开发期未查看。冻结后一次性配对运行。

## 18. FINAL_TEST results

| Variant | Engine win | Clean win | USV loss | UAV loss | Breakthrough |
|---|---|---|---|---|---|
| V4 DEFAULT | 19/20 (95%) | **18/20 (90%)** | **0.75** | 0.25 | 0.05 |
| V4 DeepSeek | 19/20 (95%) | 17/20 (85%) | 1.15 | 0.25 | 0.10 |

Commander 行为（DeepSeek 侧）：calls 12.15、changes 10.8、no_change 1.35、
policy_failures 0.05、api_failures 0.0、latency 5.23s。

### Paired-seed classification（20 seeds 逐一配对）

```
both_win     : 16   [201,202,204,205,206,207,208,211,212,213,214,216,217,218,219,220]
default_only :  2   [210, 215]
deepseek_only:  1   [209]
both_lose    :  1   [203]
```

**净效果**：DeepSeek 相对 DEFAULT 的干净胜率 = +1（209）− 2（210/215）= **−1/20**；
平均 USV loss +0.40（0.75→1.15）。

## 19. Commander marginal-value analysis

### 是否真调用 / 是否改变行为
是。`commander_source=deepseek` 全 20 局、0 次 provider/parse 失败；意图字段
（focus/reserve/overmatch/recon_mode/unc_tol）在模型输出中全维度变化，且已接入
确定性控制器（allocator 阈值、guard、UAV 门槛、USV band）→ **Commander 确实改变了
下游行为**（非"只出文本无作用"）。

### 改变是否有益（paired）
- **both_win 16/20**：两种变体都赢，多数情况下意图差异未改变胜负结局。
- **deepseek_only 1（seed 209）**：DEFAULT=quirk（5 USV loss、1 突破），
  DeepSeek=clean（0 loss）。DeepSeek 识别"black_usv1 已有 3 攻击者 → 避免过度集中"、
  "单艘高威胁丢失→先重搜确认再提交"，避免过度提交 → 干净获胜。**Commander 提供
  边际正价值的唯一案例。**
- **default_only 2（210、215）**：DEFAULT=clean，DeepSeek=quirk。两条都是同一模式：
  DeepSeek 高频输出 `reserve_ratio=0.00 + focus=3/overmatch=decisive/unc_tol=0.2`，
  4 艘快速击杀后第 5 艘完全逃出跟踪（`TRACKS vis=0`），剩余 USV 找不到它而被其
  反杀（USV 2/5→0/5），最终突破→quirk。激进意图放大了"最后 1 艘漏网"风险。
- **both_lose 1（seed 203）**：两变体都输（4 杀后第 5 艘逃跟踪→USV 全灭→UAV 全灭）。
  属于确定性层也未解决的顽固失败模式（见 §20）。

### discordant 时间线（intent→allocation→outcome）
- seed 209（DS 赢）：DS 意图 `overmatch=balanced reserve=0.2`，明确"避免 overcommit"→
  allocator 覆盖 5 艘后保留 1 预备 → 第 5 艘被保住覆盖并被击杀 → clean。
- seed 210（DS 输）：DS 意图 `focus=3 reserve=0.0 overmatch=decisive unc_tol=0.2` →
  allocator 全量提交 + 3v1 集中 → 前 4 艘快速击杀，第 5 艘（跟踪被丢）无覆盖、
  无人重搜成功 → 反杀 4 艘 USV → quirk。
- seed 215（DS 输）：同 seed 210 模式（`reserve=0` + screen/reacquire 高频切换）。
- seed 203（双输）：两变体前 4 杀一致，第 5 艘逃跟踪；确定性层 coverage/last-ship
  fallback 未能补救（跟踪完全丢失，UAV reacquire 失败）→ 双输。

### 结论性统计
- 决策质量：DS 在 16/20 上与 DEFAULT 持平、1 局更好、3 局更差。
- 失败分布：所有 discordant/loss 局（203/209/210/215）都落在同一"最后 1 艘逃跟踪
  的对杀 RNG"机制上；样本内差异与 combat RNG 噪声同量级（±1~2 局）。
- **净边际价值 ≈ 0~略负**：DEV −3、FINAL −1（clean），USV loss 更高。

## 20. remaining failure modes

1. **"最后 1 艘逃跟踪"**（占全部非 clean 局）：前 4 杀后第 5 艘完全从 TrackManager
   消失（`TRACKS vis=0 lost=0`，连 lost track 都无），UAV reacquire 失败，剩余 USV
   找不到它而被反杀；若它突破则 quirk。这是确定性层当前未闭环的盲区：对完全丢失的
   最后一个高威胁，coverage/last-ship fallback 因"无 track 可分配"而失效。
   候选修复（未来）：对"最近从可见转为全丢失"的敌舰保留更长记忆 / 区域搜索；在
   击杀计数 < 预期敌舰数时强制 UAV 全域扫描。
2. **DeepSeek 激进意图（reserve=0 + decisive + low unc_tol）**在 1、3 类失败上
   放大风险：它把确定性层本就拉满的提交进一步拉满，缩短了"信息先于提交"的余量。
3. UAV 偶发损失（FINAL 0.25/局）：母船沉没连带 / 极个别其它路径，非系统性。

## 21. final recommendation

**结论：DETERMINISTIC DOMINANT。**

- V4 确定性 harness 在 10v10 random-waypoint 上已很强：FINAL 18/20 clean、
  USV loss 0.75、UAV loss 0.25、0 崩溃、0 公平性违规。
- 真实 DeepSeek Commander 接入正确、安全、可观测（source 全 `deepseek`、
  0 provider/parse 失败、低频 12 次/局、非阻塞、fallback 链完好、政策校验通过），
  且确实改变下游行为（意图字段真实作用于 allocator/UAV/USV）。
- 但**边际价值不显著为正**：FINAL paired −1 clean（1 正 2 负）、USV loss 更高；
  DEV −3。唯一正案例（209）来自模型正确执行"避免过度集中/信息先于提交"——该原则
  已写入 SKILL 且确定性层本身已部分编码。未能证明 LLM 带来确定性层不具备的收益。
- **建议**：保留确定性架构为 primary；Commander 可作为**可选战略覆盖层**保留
  （LLM OPTIONAL 方向），但不应作为胜率来源依赖。若继续使用，应进一步 clamp 其
  `reserve_ratio=0 / focus=3 / decisive` 组合（或默认更多 reserve），并优先补上
  "最后 1 艘逃跟踪"这一确定性盲区——该修复对胜率的预期收益远大于 Commander 微调。

---

## 附录 A：公平性审计

`agent_hybrid_v4.py` runtime 区（`def selftest_trackmanager` 之前）对以下模式零命中：
`black_usv / black_uav / black_strategy / BLACK_Y / ENEMY_X / 260000 / vx=-10 /
random_waypoint / waypoint_seed`（test_v4_units.py `test_path_agnostic_and_fair_play`
自动化验证）。SKILL / Commander prompt 亦零命中。Agent 不知 seed、不知航路生成规律。

## 附录 B：Verification / Inference / Hypothesis

- **Verified**：DeepSeek 真实调用（HTTP 200 + source=deepseek + 0 API failure）；
  意图字段接入确定性控制器；FINAL paired 16/2/1/1；Commander 行为统计；公平性零命中。
- **Inference**：DeepSeek 净边际价值 ≈ 0~略负（样本小，差异与 RNG 同量级）。
- **Hypothesis**：激进意图（reserve=0+decisive）放大"最后 1 艘逃跟踪"失败；
  "最后 1 艘逃跟踪"修复对胜率收益 > Commander 微调。
