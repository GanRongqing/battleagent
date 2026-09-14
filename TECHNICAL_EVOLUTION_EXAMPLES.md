# 具体技术进化案例

> 本文件只使用当前项目真实 artifact / 真实 diff / 真实运行 evidence。
> 不改代码、不重新生成 Skill、不编造例子。
> Skill 进化 ≠ 代码进化；StrategicIntent 更新 ≠ Skill 进化。

---

# Case 1 — Skill Evolution：Coverage vs Concentration

## 1. 真实问题（运行现场）

来源：`runtime_audit/run_ep4_1787234142/step_336.json`（DeepSeek 局，sim_time=6598s）

```
mission        = NORMAL_COMBAT
trigger        = lost_high_threat
coverage       = quality 0.161（29/56 cells 被覆盖）
enemy ships    = 5 艘，全部在 cluster_1（4 visible / 1 lost，recon_coverage=low）
```

| track | 状态 | 已投入的 USV |
|---|---|---|
| black_usv3 | **lost**（visible=False, age=64s, unc=6880m, conf=0.5, point_confidence=1.0） | **white_usv1, white_usv2, white_usv5（3 艘）** |
| black_usv2 | visible（age=0, conf=1.0） | white_usv3, white_usv4（2 艘） |
| black_usv4 | visible | **0 艘（未覆盖）** |
| black_usv1 | visible | **0 艘（未覆盖）** |
| black_usv5 | visible | **0 艘（未覆盖）** |

当前 StrategicIntent（E 层，deepseek，本步生效）：`posture=balanced focus=2 emergency=3 reserve_ratio=0.00 reserve_usvs=auto ... uav_mode=search_and_reacquire recon_mode=screen_priority`

allocator 行为：`result={} margin=None` —— 5 艘 USV 已全部处于 committed，`avail=0`，本步无法再产生新分配。

本步应用的新 Commander 响应（request_id=10）：`reserve_ratio=0.10, uav_mode=focused_reacquire, uav_priority=[black_usv3], recon_mode=reacquire_priority`
reason（原文）：`lost track black_usv3 has 3 attackers already and moderate uncertainty; prioritize reacquire to maintain coverage while retaining small reserve for unpredictable threats.`

**当时发生了什么：** 一条已丢失 64s、不确定半径 6.9km 的敌舰，被 3/5 的 USV 追击（over-concentration on an uncertain target），同时有 3 艘可见敌舰 0 覆盖。Commander 自己也意识到了 tension（reason 里说 "prioritize reacquire to maintain coverage"），但当时的 Skill 文档并没有给出"覆盖缺口 vs 边际集中"的优先级原则，只有针对单目标不确定性的 guard。风险：若丢失目标预测失准，3 艘 USV 扑空，而 3 艘可见敌舰无人对抗（min_breakthrough_x=194044，尚不构成即时突破）。

## 2. Skill Before

旧文件 `skills/maritime_commander/history/SKILL_aebc47bf8632.md` 中相关条文：

**## Uncertainty semantics**（高不确定）
> 高不确定：优先改善信息（UAV reacquire），避免对陈旧点估计做昂贵且不可逆的集中。
> 除非突破风险即刻存在，必须立即拦截。

**## Low-confidence commitment**
> 低置信接触 + 大不确定区域 → 避免昂贵且不可逆的集中。
> 除非：突破风险即刻存在（必须拦截）；或等待其它信息源的危险更大。
> 这通过 `uncertainty_tolerance` 表达（低 = 更谨慎提交 USV，高 = 更愿意冒信息不确定的风险）。不确定性是提交决策的输入，不是直接命令。

这条旧 doctrine 能告诉 Agent：对单个低置信/丢失目标，不要做昂贵不可逆的集中。
它缺少的：**当"多个威胁区域存在覆盖缺口"时，修复覆盖 vs 继续向单个目标追加边际集中的优先级关系**——旧文只约束"对不确定目标本身的提交"，没有约束"全局覆盖缺口下的资源排序"。这正是 EVID-001 场景（3 艘未覆盖 vs 1 艘被 3 艘追击的 lost track）需要的指导。

## 3. 系统如何判定这是 Skill/doctrine 问题

`classify_evidence`（skill_evolution.py，确定性启发式，逐条落盘）：

```
primary = STRATEGIC_DOCTRINE
categories = [RECON, STRATEGIC_DOCTRINE]
skill_change_justified = true
decision = PROCEED
root_cause = lost ship overcommitted (≥3 attackers) while 3 ships uncovered at
             coverage=0.16 → doctrine ambiguity about information-before-commitment
```

ROOT CAUSE：
- primary = **STRATEGIC_DOCTRINE**（信息优先 vs 集中的优先级在文档中缺失/含糊）
- secondary = **RECON**（信息/覆盖恢复优先）

为什么不是 allocator bug：证据中 allocator 返回 `{}` 是**正常工作**——它按 marginal utility + coverage floor 分配，本步所有 USV 已 committed（`avail=0`），无新增可分配。它不是"算错了分配"，而是高层 doctrine 没有告诉 Commander 在覆盖缺口下如何调整 reserve/overmatch 方向。这不是 perception/TrackManager/controller bug（无感知异常、无航迹丢失逻辑错误）。

## 4. Analyst 提议了什么

`analyst_output.json`（外显结构化输出，无 chain-of-thought）：

```
evidence_refs      = ["EVID-001"]
skill_change_needed = true
scope              = general
confidence         = 0.7
root_cause         = 5 艘敌舰全可见、3 艘未覆盖、coverage 0.161，但丢失目标仍被 3 艘 USV
                     集中 → 现行文档对"信息不确定时是否减少集中以维持覆盖"缺少明确指导。
problematic_doctrine = Low-confidence commitment 未与 coverage 结合；Local force
                      concentration 未说明"低置信目标过度集中会违反覆盖目标"。
proposed_principles =
  1. 当多个敌方威胁未受覆盖时，任何目标的攻击者分配不得超过维持全局覆盖所需的兵力余量。
  2. 低置信目标不构成比未覆盖目标更高的优先权：覆盖/信息缺口更大时优先恢复覆盖与侦察。
  3. 覆盖质量（coverage quality）应作为集中力度的输入——覆盖显著低时默认降低 overmatch。
```

即 Analyst 提出了 3 条，其中**包含硬性/量化成分**（"不得超过兵力余量"、"coverage 作为输入/默认降低"）。

## 5. Critic 否掉了什么

`critic_output.json`：`accept_analyst = false`，confidence=0.85

逐条表决（都是 Critic 输出中真实存在的理由）：

| Analyst 提议 | Critic 判定 | 真实理由（原文要点） |
|---|---|---|
| 1. 分配不得超过全局覆盖所需余量 | **REJECT** | 把分配细节写进 Commander 文档，越权到 allocator 职责，违反 `Commander role` 边界 |
| 2. 低置信目标优先级低于未覆盖目标 | 部分接受（并入最小原则） | 本身不引入数字，方向可接受 |
| 3. coverage quality 作为集中力度输入 | **REJECT** | 绑定具体 harness 指标/阈值，场景化，不该写进长期 doctrine |
| （隐含）用单步证据重写 doctrine | **REJECT** | **过拟合风险**：EVID-001 仅单局单步，uncovered_ships=3 可能源于分配器/信息延迟 |
| （隐含）硬阈值/离散门槛 | **REJECT** | **泛化风险**：不同规模/地图下 coverage 含义不同；且与 allocator coverage floor 职责重叠 |

Critic 同时给出一类反例（原文要点）：endgame 只剩 1 艘高威胁敌舰时，硬性"不得追加"规则会阻止正确集中，与 Endgame doctrine 冲突。

## 6. Editor 最后改了什么

`editor_output.json`：`decision=MODIFY`，只保留 1 条最小、定性、规模无关的表述。

- accepted：在 `Low-confidence commitment` 增加一句"覆盖缺口优先于边际集中"
- rejected：具体分配规则（越权 allocator）、coverage 指标输入（绑定阈值）、基于单步证据重写（过拟合）

**BEFORE**
```text
这通过 `uncertainty_tolerance` 表达（低 = 更谨慎提交 USV，高 = 更愿意冒信息
不确定的风险）。不确定性是提交决策的输入，不是直接命令。
```

**AFTER**
```text
这通过 `uncertainty_tolerance` 表达（低 = 更谨慎提交 USV，高 = 更愿意冒信息
不确定的风险）。不确定性是提交决策的输入，不是直接命令。

**覆盖缺口优先于边际集中**：当多个敌舰未受覆盖时，修复覆盖比追加对单一目标的
火力更有价值。
```

**EXACT DIFF**（`skill_evolution_runs/evo_losttrack_coverage/skill.diff`，lines changed = **+2**）
```diff
--- skill_before.md
+++ skill_candidate.md
@@ -155,6 +155,9 @@
 这通过 `uncertainty_tolerance` 表达（低 = 更谨慎提交 USV，高 = 更愿意冒信息
 不确定的风险）。不确定性是提交决策的输入，不是直接命令。
 
+**覆盖缺口优先于边际集中**：当多个敌舰未受覆盖时，修复覆盖比追加对单一目标的
+火力更有价值。
+
 ---
```

## 7. 验证

`validation.json`：

- Static audit：**PASS**（`added_violations=[]`；仅 2 条 added=False 的信息性命中，即旧文自身禁止"固定敌方数量"的措辞）
- Schema：analyst/critic/editor 全部通过
- Unit / fair-play tests：**6/6 全部 rc=0**（test_v3 49、v4 41、v5 37、v6 49、audit_variable_cardinality 15/15、audit_scale_generalization 13/13）
- Tiny regression（candidate 装入后跑真实对局，seed=7）：

| Scenario | result | 时长(sim) | parse 错 | api 错 | policy 错 | invalid/异常 | latency |
|---|---|---|---|---|---|---|---|
| 5+5 Harness | Result.Victory | 14236 | 0 | 0 | 0 | 0 | – |
| 10+10 Harness | Result.Victory | 13381 | 0 | 0 | 0 | 0 | – |
| 5+5 Commander | Result.Victory | 11469 | 0 | 0 | 0 | 0 | 3.4s |

基线（候选前同场景）：5+5 Commander latency=3.7s、parse/api/policy=0、Victory → 无粗回归。

## 8. 发布与回滚

```
old hash        = aebc47bf863207dcf49206c6e13e81b3ea62417f5ff752135f14133c72acda24
new hash        = 155b02019dc92c6e6c0095949439a413cd86310ad1026cd394ad185c3d13552e
approval        = APPROVED by operator（显式 --approve；默认 PENDING 不安装）
release version = 1
backup          = skills/maritime_commander/history/SKILL_aebc47bf8632.md
rollback target = aebc47bf863207dcf49206c6e13e81b3ea62417f5ff752135f14133c72acda24
version record  = skills/maritime_commander/history/versions.jsonl（v1）
```

运行中的 Skill 不变：`agent_hybrid_v5.py` 对 SKILL.md 只读（无任何 write-open/replace/copy）。
只有 offline evolution → validation → explicit approval 才会替换 SKILL.md。`--rollback <hash-or-version>` 按 hash 校验精确恢复旧文件（已验证：diff 为空）。

---

# Case 2 — Harness Evolution：Lost Track → Global Reacquire

> 属于 **Harness / 代码进化**，不是 Skill 进化。

**Before（V4）**：`agent_hybrid_v4.py` 中 `GLOBAL_REACQUIRE` 出现次数 = 0。当 `cur is None`（无目标）时，USV 只向东巡逻（`pos[0]+100000`），没有 mission 级的全局重搜；把所有已知敌舰击沉/丢失后，剩余未被探测的敌舰可能长期不被发现而悄悄突破。

**After（V5）**：`agent_hybrid_v5.py` 新增 mission 状态机 `_compute_mission`（L2744）：
- 触发条件（不依赖敌方总数）：`/result` 未结束 AND 无可靠 hostile USV track（可见或丢失但有位置）AND 无有效锁定链 AND 已曾见敌舰 AND 持续 ≥ `GLOBAL_REACQUIRE_DELAY=90s`
- 行为：可用 USV 收敛到防御屏列 `SCREEN_X=120000`（`agent_hybrid_v5.py:2065`）；UAV 进入 GLOBAL_SEARCH；Commander 触发 `trigger=global_reacquire`

**真实运行 evidence**（`logs_asy/A_deepseek_s302.log`）：
```
t=10,353s  [KILL] black_usv7  → 全部已知敌舰清空（TRACKS: vis=0 lost=0, KILL=7）
t=10,564s  MISSION=NORMAL_C → GLOBAL_R（90s 滞回到期，USV avail=4 屏列，UAV air=5）
t=10,725s  [COMMANDER REQUEST] trigger=global_reacquire
t=10,785s  MISSION=GLOBAL_R → NORMAL_C（重新探测到敌舰，TRACKS: vis=1）
（随后再次进入/退出 GLOBAL_R，最终全局 entries=2 / success=2，Victory@13218s）
```

单测：`test_v5_units.py` `test_global_reacquire_unknown_enemy_count`（不依赖敌方总数进入 GLOBAL_REACQUIRE）、`test_global_reacquire_exit_on_detection`（恢复时计数 success）。

**一句话：从"丢光已知目标后盲目东巡"进化到"mission 未解决 → 无可靠战斗航迹/无有效交战 → GLOBAL_REACQUIRE 屏列 + 全局重搜，重新探测即恢复"。**

---

# Case 3 — Runtime Evolution：Async Response → Versioned Response

> 属于 **runtime concurrency correctness 进化**，不是 Skill 进化。

**Before**：`LLMCommander._worker` 完成异步 LLM 后无条件 `latest_intent = intent`，无 generation/版本校验。若响应返回时状态已变化，旧响应会覆盖新状态（审计 §4 记录的 stale-response 竞态）。

**After**：每个请求带 `request_id / generation / source_step_id / source_state_signature`；`_latest_observed_sig` 每步推进；worker 完成时校验 source sig 是否仍为最新，不匹配则 **STALE_REJECTED**，`last_valid_intent` 保持不变（`agent_hybrid_v5.py` LLMCommander）。

**真实 evidence**（`runtime_audit/run_ep4_1787234142`）：13 次 Commander 响应，**9 applied / 4 STALE_REJECTED**（与 [META] `commander_calls=13 commander_changes=9` 一致）。

真实被拒案例（`step_211.json` D 记录 + 控制台日志）：
```
STALE step=211 req=6 src_step=211 sim=3868 applied=False parsed=None rejected_reason=stale_rejected
[COMMANDER] STALE_REJECTED request_id=6 source_step=211 using=last_valid_intent latency_real=3.1s
其余：req=11/src=363、req=12/src=389、req=13/src=414
```
单测覆盖：`test_v6_audit_units.py` `test_stale_response_rejection` / `test_current_response_acceptance`。

**一句话：从"异步响应返回即覆盖，可能应用过期状态"进化到"带 request_id/generation/source_step_id/state_signature 的版本化响应，过期响应 STALE_REJECTED 且保留 last-valid intent"。**
