# AUDIT_RUNTIME_SKILL_REVIEW.md

> 只读式技术审计 / verification audit。不修改 Agent / Skill / Prompt / 仿真。
> 判定标准：`CODE > DESIGN DOCUMENT`、`RUNTIME LOG > CLAIM`、`ACTUAL API PAYLOAD > INTENDED SCHEMA`、
> `MISSING EVIDENCE ≠ PASS`。无证据即判 `NOT IMPLEMENTED` 或 `PARTIAL`。
> 审计日期：2026-08-19

---

## 1. Executive Summary

- **Runtime chain 已确认**：Agent → HTTP(POMDP API /status+/legal_actions+/apply+/result) → 引擎。
  Agent 是独立 HTTP 进程，不 import engine、不直连 gRPC。
- **决策步（decision step）**：无显式持久化 `step_id`。`self.step` 是主循环计数，与 API 侧
  `/apply` 的 step 计数、evaluator 轮询样本之间**无任何关联键**。
- **LLM 机制**：event-gated（非每步调用），有 in_flight/cooldown/state-sig 门控与
  no-change 滞回；**但无 stale-response 保护（无 generation/version 校验）**——旧 LLM 响应
  可能在新观察后仍被应用。
- **六层证据 A→F**：A(partial 落盘于 API game_log 摘要)、F(partial 落盘于 API game_log)，
  B/C/D/E **未持久化**。**无法按任意 step_id 重放 A→F。**
- **Truth leakage（静态）**：runtime 零命中 black-truth；`/status` 白名单不透出 black states。
  存在设计性 L4 身份泄漏（被动告警暴露敌名）；理想共享感知（无通信延迟/丢包模型）。
- **Anti-leak T1–T4**：T1/T3/T4 NOT IMPLEMENTED；T2 PARTIAL。
- **Skill**：冻结文件（当前 hash aebc47bf…），启动时读一次，**无在线更新**；有历史 hash
  记录（e1f7839a→aebc47bf）但无 git diff；**无完整可审计的 Skill 更新闭环**；**无 LLM
  self-discussion**。
- **明天可安全声称**：见 §15；**明天不可声称**：见 §16。

---

## 2. Actual Runtime Chain

### 2.1 链路（文件/class/函数/调用/输入/输出）

```
agent_hybrid_v5.py :: AgentMain.run()  (L2792)
  while self.step < max_steps:
    self.step += 1
    AgentMain.step_once()  (L2680)   [主循环，无显式 step_id 落盘]
      |-- ApiClient.status()  (L156) -> GET /status   [原始 JSON 入内存，未落盘]
      |     -> Obs(st, now) (L201)  [now = parse_sim_time(局内时间)]
      |-- ApiClient.legal_actions() (L162) -> GET /legal_actions -> LegalSet (L235)
      |-- TrackManager.update/reconcile_assigned/kill_detect  (L2690-2695)
      |-- _compute_mission / _update_coverage_from_usvs  (L2698-2700)
      |-- ThreatAllocator.allocate_usvs(..., return_margin=True) (L2704) -> (alloc, margin)
      |-- USVController.step / UAVManager.step  (L2710-2715)
      |-- _record_stats / FriendlyResourceState.build / ThreatClusterBuilder.build (L2719-2724)
      |-- TacticalSummarizer.build_v5(...) -> summary_text  (L2725)
      |-- _detect_trigger / _state_signature / _commander_ctx  (L2728-2730)
      |-- LLMCommander.maybe_request(...)  (L2731, spawn daemon thread, 非阻塞)
      |-- ActionSafety.filter  (L2741)
      |-- ApiClient.apply(safe)  (L2745) -> POST /apply   [fire-and-forget]
      `-- _maybe_log  (L2750, 每 LOG_INTERVAL=10 步打印聚合)
  GET /result  (L2811, 仅对局结束后) -> _print_meta -> _dump_commander_audit -> GET /stop
```

引擎侧（独立进程，Agent 不接触）：
```
sim_server (:6001) -> temp.sim() -> scenario_builder.build_scenario / scenario_composition.sim()
  -> TzbEngine -> engine.update()（ratio=100 后台线程持续运行，从不等待 Agent）
pomdp_api (:8000) -> gRPC base_server (:6000) -> sim_server
```

### 2.2 五个问题

1. **Agent 是否只通过 HTTP API 获取运行时信息？** YES。`ApiClient` 只调用
   `/start /status /legal_actions /apply /stop /result`（`agent_hybrid_v5.py:154-172`）。
   `/obs` 已定义但 `0` 次调用。
2. **Agent runtime 是否直接 import simulator engine？** NO。`agent_hybrid_v5.py` 无
   `import simulation.*`（truth-leakage 扫描 0 命中）。
3. **Agent runtime 是否直接调用 gRPC simulator？** NO。无 `grpc`/`base_server`/`sim_server` 引用。
4. **Agent 是否有路径拿到 black-side runtime truth？** 无直接路径。`/status` 白名单
   （`main.py:1605-1646`）只透出 `white_usv_states`/`white_uav_states`/`white_observation`
   （雷达捕获=探测到的敌舰 truth，被动告警=方位+名）。`black_usv_states`/`num_black_*` 不透出。
   唯一间接信息：`奖励信号`（black_killed/hit/breakthrough 累计）与被动告警中的敌名（L4 身份）。
5. **Commander 输入从哪些对象构建？** `TacticalSummarizer.build_v5(obs, tracker, usv_ctrl,
   uav_mgr, intent, resource, clusters, coverage, mission, now)`（L2725-2727）→ `summary_text`；
   `LLMCommander.build_system_prompt()`（L1496）= `COMMANDER_ROLE + SKILL.md + INTENT_SCHEMA_DOC`；
   `_safe_call(summary_text)`（L1604）→ `user = "CURRENT TACTICAL STATE:\n\n{summary_text}..."`。

---

## 3. Definition of Decision Step

### 3A. control-loop 类型：HYBRID（轮询 + fire-and-forget）
- 证据：`run()` 循环每次 `sleep(0.05)` 后 `step_once()`（L2807）；引擎在后台线程**持续推进**
  （sim_server 的 `engine.update`），Agent 的 `/apply` 是 fire-and-forget（命令持久生效）。
- 因此既不是严格 fixed-period actor（引擎不等 Agent），也不是干净 event-driven（Agent 每步轮询
  /status 获取状态）。**hybrid**。

### 3B. step 真实边界
- 无显式 `step_id`。循环每次迭代 = 一个决策回合（一次 /status 观察 → 一次 /apply）。
- 观察截止：`GET /status` 返回时刻的状态快照。
- 决策：`step_once` 内同步完成（除 LLM 后台线程）。
- 动作应用：`POST /apply`。
- 下一反馈：下一次 `/status`（Agent 端）或 API game_log 的下一 StepRecord。
- **CURRENT SYSTEM HAS NO EXPLICIT AUDITABLE STEP_ID**（`self.step` 是循环计数，每 10 步才打印，
  不持久化，且与 API/评估侧计数无关联键）。

### 3C. 时间戳

| 事件 | 存在？ | 字段 | 代码 | 日志 |
|---|---|---|---|---|
| simulation time | YES | 局内时间 HH:MM:SS → 秒 | parse_sim_time (L189)；Obs.now | agent `_maybe_log` `[t=...]`；API game_log `sim_time` |
| wall-clock time | PARTIAL | API game_log `real_time`（/apply 时刻）；agent 仅 start/end | main.py:403；run() start | game_*.json |
| monotonic time | NO | — | — | — |
| obs receive | NO（agent 侧）；API game_log 的 real_time 近似于 apply 时刻快照 | — | — | game_*.json real_time |
| LLM request | PARTIAL | audit `sim_time`（请求时仿真秒） | LLMCommander audit (L1550...) | commander_audit_seed.json；agent log `[COMMANDER REQUEST] t=...` |
| LLM response | PARTIAL | audit `latency`(real s) + `sim_time` | L1541/1599 | commander_audit_seed.json；agent log `[COMMANDER RESPONSE]` |
| allocator done | NO | — | — | — |
| apply | YES（API 侧） | API game_log `real_time`+`sim_time` | main.py:399-403 | game_*.json |
| next feedback | YES（API 侧） | 下一 StepRecord | main.py:412 | game_*.json |

---

## 4. Timing and Concurrency

- async Commander：YES（`threading.Thread`, daemon, L1531-1535）。
- lock：YES（`threading.Lock`, L1482）。
- queue：NO。
- timestamp：sim_time + latency（real s），无 wall 时间戳。
- message id / step id / generation id / request id：**NO**。

### A. 旧 LLM 响应是否可能在新观察后应用？
**YES（存在竞态）**：`_worker`（L1538）完成时无条件 `self.latest_intent = intent`（L1591），
不检查发起请求时的观察是否仍是最新。后台线程调用期间主循环继续推进，若状态已变，旧响应仍被应用。

### B. generation/version check？
**NO**。无任何"请求对应的 state 版本"标识。

### C. stale response rejection？
**NO**。没有拒绝机制。

### D. observation 有 timestamp/age？
有 sim_time（`Obs.now`）。无显式 age 字段（age 由各消费方用 `now - last_seen` 自己算）。

### E. duplicate observation 处理？
无去重逻辑——每步重新轮询，重复观察自然覆盖；无 message dedup。

### F. cross-step message 处理？
N/A——无消息队列/跨步消息。Commander 意图在后台线程写入 `latest_intent`，主循环下步读取；
这是唯一的"异步跨步"路径，且无版本保护。

**结论：并发处理 = PARTIAL（异步存在；stale-response 防护 NOT IMPLEMENTED）。**

---

## 5. Six-Layer Step Evidence Audit (A–F)

### Layer A — Raw Observation
- Runtime：YES（`GET /status` JSON → `Obs.status` 内存；`/legal_actions` → `LegalSet`）。
- Persisted：**PARTIAL**。API game_log（`api_logs/games/game_*.json`，每 `/apply` 一个
  StepRecord）落盘的是**白名单摘要**（`main.py:358-383`：usv/uav 的 name/alive/position/
  speed/course/is_locked/is_locking/is_frozen/locked_attacker/locked_times/battery_pct +
  active/passive enemies + delta reward + events），**不是原始 /status JSON**。
- keyed by API step（每次 /apply 递增），与 Agent 循环 step **无关联**。
- Timestamp：sim_time + real_time（game_log）。

### Layer B — Legal Fused State
- Runtime：YES（TrackManager / FriendlyResourceState / CoverageMap / ThreatClusterBuilder /
  MissionState 全部在内存）。
- Persisted：**NO**。无 track/confidence/age/uncertainty/resource-ratio/clusters/mission 落盘。
- 变量来源合法（全部来自 /status 白名单 + 自身推断）。

### Layer C — Actual LLM Context
- Runtime：YES（`build_system_prompt()` + `summary_text` 每步构建）。
- Persisted：**NO**。`summary_text` 未落盘；audit 只存 `intent.describe()`。
- **无法重建 exact API payload**（缺 system/user 全文、Skill 版本注入、state 快照）。
- **PARTIAL**（不可重建精确上下文）。

### Layer D — Raw LLM Output
- Runtime：YES（`call_commander_llm` 返回 raw text，L940）。
- Persisted：**NO**。`raw` 解析后丢弃；audit 只存 parsed/clamped `intent.describe()` + latency +
  source + trigger + sim_time + parse_success/policy_success/fallback_reason。
- **Raw text、token usage、provider 原始响应未保存**。
- Parse error reason（如 `parse_error(malformed_json)`）记录，但 raw 文本不存。

### Layer E — Intermediate Result
- allocator：返回 `(result, margin)`（L2706）——**只保存最终分配与 best-second margin**，
  未保存 cost/utility 矩阵、候选列表、controller 每艇 target 的中间过程。
- 无持久化。**无法恢复分配轨迹**。

### Layer F — Execution Feedback
- Runtime：YES（`/apply` response）。
- Persisted：**PARTIAL**（API game_log 的 StepRecord.actions：动作文本/成功/跳过/详情）。
- ActionSafety 的过滤结果**未落盘**（哪些候选被过滤、为何过滤，无记录）。
- controller FSM state（USV/UAV 状态机）未落盘。

> **Current executor is controller/FSM-based rather than Behavior Tree.**（无 BT；控制器是
> 每步在内存中计算的 FSM 状态机，状态未持久化。）

---

## 6. A–F Step Trace Matrix

| Layer | Runtime exists | Persisted | Replayable by step_id | Timestamped | Missing evidence |
|---|---|---|---|---|---|
| A Raw observation | YES (/status JSON in memory) | PARTIAL (API game_log 白名单摘要) | NO (API step≠agent step) | sim+wall(game_log) | 原始 /status JSON；agent 侧 step 关联 |
| B Fused state | YES (in-memory) | NO | NO | NO | tracks/resource/clusters/mission 落盘 |
| C LLM context | YES (built each step) | NO | NO | NO (仅请求时 sim_time) | 精确 system/user payload；summary 落盘 |
| D Raw LLM output | YES (raw text transient) | NO | NO | NO | raw response；token usage；retry |
| E Intermediate | YES (alloc result+margin) | NO | NO | NO | cost/utility 矩阵；candidates；controller 中间态 |
| F Execution feedback | YES (/apply resp) | PARTIAL (API game_log actions) | NO | sim+wall(game_log) | ActionSafety 过滤记录；FSM 态 |

**Can an auditor currently choose arbitrary step_id and reconstruct A→F?**
**NO。**（B/C/D/E 未持久化；step_id 关联缺失；A/F 仅 API 摘要且与 agent step 无键。）

---

## 7. Example Real Step Trace

选取 logs_asy/A_deepseek_s301.log（真实 DeepSeek 局）中信息最全的一刻（t=2211s, lost_high_threat）：

```
run_id:  logs_asy/A_deepseek_s301.log（对局 19，scenario_composition，A: 5+5 vs 8+7）
step/loop identifier: NOT RECORDED（无显式 step_id）

OBS:  NOT RECORDED（原始 /status 未落盘；game_log 有 API 侧摘要，但与此步无键关联）
FUSED: NOT RECORDED（TrackManager/resource/clusters/mission 未落盘）
COMMANDER: called=yes  trigger=lost_high_threat
  input summary: NOT RECORDED（TacticalSummarizer 输出未落盘）
  raw context available: NO
  raw output available: NO（raw 文本解析后丢弃）
  parsed StrategicIntent（日志可见）:
    posture=aggressive focus=2 emergency=3 reserve_ratio=0.20 priority=['black_usv1','black_usv8','black_usv7']
    uav_mode=focused_reacquire uav_priority=['black_usv1'] recon=0.8 engage=0.8
    overmatch=balanced recon_mode=reacquire_priority standoff=medium unc_tol=0.30
    reason='8 visible USVs closing, 3 uncovered high-threat tracks; ...'
  validation/clamp: 未记录是否触发 clamp（audit 有 policy_success 布尔，但该局 audit 未保存）
  latency: 2.1s real (≈106 sim-s)
  downstream effect: NOT RECORDED（allocator/controller 结果未落盘）
ALLOCATOR: NOT RECORDED
CONTROLLER: NOT RECORDED
ACTION: NOT RECORDED（agent 侧；API game_log 有该 /apply 的 actions 摘要但无键关联）
NEXT FEEDBACK: NOT RECORDED（无关联）
```

缺失项统一标注：**NOT RECORDED**。

---

## 8. LLM Input Provenance

| field | exact source | source level | creation time? | age/confidence? | runtime legal? |
|---|---|---|---|---|---|
| FRIENDLY usv/uav | /status white_usv/uav_states 白名单 | L0 (own measurable) | sim_time | 无 age；无 confidence | YES |
| enemy tracks(active) | /status 雷达捕获 = get_white_targets（探测到的敌舰 truth 位置/速度） | L3 (simulator truth via observation) | last_seen | confidence/uncertainty/age（TrackManager 派生） | YES |
| enemy passive | /status 被动告警 = locked_attacker 名+方位 | L4 (identity, 方位) | — | — | YES（设计性 L4） |
| resource ratios | 由 /status 白名单聚合（FriendlyResourceState） | L0/L2 | sim_time | — | YES |
| mission_state | /status ended + 自身 tracker 推断 | L2 | sim_time | — | YES |
| coverage | CoverageMap（由白方单位位置推断） | L0/L2 | sim_time | coverage_age（内部） | YES |
| threat_clusters | ThreatClusterBuilder（由 tracks 推断） | L2 | sim_time | avg_conf/visible/lost | YES |
| history | **不包含**（V5 TacticalSummarizer 无动作历史字段） | — | — | — | — |
| last intent | 当前 intent（CURRENT COMMANDER INTENT 段） | L0 (own) | — | — | YES |
| skill | SkillLoader.load()（SKILL.md 冻结文件） | L0/design | 启动时 | 无 | YES |
| prompt | COMMANDER_ROLE + INTENT_SCHEMA_DOC（代码常量） | L0/design | 代码 | 无 | YES |

- 通信语义：**shared-sensing API semantics**（`get_white_targets` 为全部 RED intel 目标并集），
  不是显式 packet-level 通信协议。

---

## 9. Truth-Leakage Audit（静态）

Runtime 区（`def selftest_trackmanager` 之前，agent_hybrid_v5.py）扫描结果：
`black_*(奖励计数)、BLACK_*、simulation.core、tzb_engine、engine.、get_state().black、
waypoint、expected_enemy、black_count、future` → **0 命中**（除 `black_killed/hit/breakthrough`
公共奖励计数与 `SCENARIO_SCRIPT` 环境变量、`SIM_RATE` 注释）。

### 七种泄漏逐项

| # | 泄漏 | 判定 | 证据 |
|---|---|---|---|
| 8.1 Entity-list | **PARTIAL** | `/status` 雷达捕获只含**已探测**敌舰；但**被动告警暴露敌名**（`_build_enemy_intel` 从 locked_attacker 取攻击者名）→ 未探测前可通过"被锁告警"得知部分敌 ID。无精确敌总数先验（`num_black_*` 不透出） |
| 8.2 Perfect-state | PARTIAL(设计) | 探测到即给**无噪声真值位置/速度**（确定性雷达）——是"探测真值"，非复制 engine 任意状态；但确实等于 simulator truth（被探测时） |
| 8.3 Communication | PARTIAL(设计) | **ideal shared sensing**（`get_white_targets` 全局并集），无延迟/丢包/断连模型。不能说成"已模拟通信延迟" |
| 8.4 Future | PASS | `/result` 只在 run() 对局结束后调用（L2811）；循环内用 `/status`（`对局结果` 仅 ended 时设置，agent 在 ended 即 break）。`奖励信号` 为累计公共计数。无未来 waypoint/terminal 泄漏 |
| 8.5 Memory | PASS(非泄漏) | TrackManager 保留 last_position/last_velocity/last_seen/confidence/uncertainty 并外推 = **信念记忆**，非真值泄漏。stale 外推被用于决策（预测即信念，V5 明确） |
| 8.6 Evaluation | PASS | maritime_metrics.py 轮询线程只 `GET /status`（只读，无注入）；run_priority_eval 只写 scenario 配置（被场景读取，非 Agent）与 `/stop`。instrumentation 不改变 Agent 输入 |
| 8.7 Identity | PASS | audit_variable_cardinality 15/15（无固定数量/ID/seed/场景分支） |

**overall fair-play（静态）：PASS**。HTTP-only、白名单 API、runtime 零 black-truth 引用。
已知设计性信息：L4 身份（被动告警敌名）、共享感知=探测真值、公共奖励计数。

---

## 10. Anti-Leak Test Status

| 测试 | 状态 | 说明 |
|---|---|---|
| T1 Hidden-state counterfactual | **NOT IMPLEMENTED** | 无"合法观测相同、隐藏真值不同 → 相同 context/action"测试。最小方案（不改 production）：用同一个 Obs 快照，注入不同 hidden truth 到 mock 引擎，断言 TacticalSummarizer 输出与 allocator 分配一致——但当前无此测试。 |
| T2 Truth masking | **PARTIAL** | Agent 是独立 HTTP 进程，构造上无 engine 对象（代码证据：无 import simulation / 无 gRPC；API 白名单即 mask）。但**无正式 assert/测试**证明"无 black-truth object 也能跑"。 |
| T3 Communication loss | **NOT IMPLEMENTED** | 无通信延迟/丢包/断连模型。TrackManager confidence 不是通信模型。 |
| T4 Delay / Noise | **NOT IMPLEMENTED** | 雷达 `fixed` 确定性、无噪声/延迟注入。 |

---

## 11. Runtime vs Persistent Changes

| Object | Runtime changes? | Development changes? | Versioned? | Rollback available? |
|---|---|---|---|---|
| Model weights | NO（固定 deepseek-v4-flash，env） | NO（外部服务） | NO manifest | N/A（外部） |
| System Prompt | NO（代码常量 COMMANDER_ROLE/INTENT_SCHEMA_DOC） | YES（跨版本重写） | 无版本号 | 源码历史 |
| SKILL.md | NO（启动时读一次） | YES（V3→V4 重写） | hash（SKILL_MD_SHA256.txt + 报告） | 无 git（根目录非 git） |
| External memory | NO（无外部记忆） | NO | — | — |
| Intermediate code | NO（agent 每局固定） | YES（V1→V5） | 报告记录 hash | 有历史文件 |
| StrategicIntent | **YES（runtime adaptive）**：Commander 更新 latest_intent，allocator/UAV/USV 消费 | schema 常量（代码） | 无 | 无 |
| Belief state | **YES（runtime adaptive）**：TrackManager/Coverage 每步演化 | — | 无 | 无 |

严格区分：runtime adaptive（StrategicIntent 值、belief）≠ persistent Skill/model update。

---

## 12. Skill Versioning

**RUNTIME（游戏内）**：
- Skill 在每局运行中保持**冻结**：`agent_hybrid_v5.py` 只在启动时经 `SkillLoader.load()`
  读一次，无任何写 SKILL.md 的代码路径（`test_skill_evolution` 的
  `test_skill_immutable_during_runtime` 扫描证明：无 write-mode open / 无 replace/copy 到 SKILL.md）。

**OFFLINE EVOLUTION（离线版本化）**：
- 冻结基线 hash：`aebc47bf863207dcf49206c6e13e81b3ea62417f5ff752135f14133c72acda24`。
- 演示发布 v1（`evo_losttrack_coverage`）：新 hash `155b02019dc9…`，已装入 SKILL.md；
  旧版备份于 `skills/maritime_commander/history/SKILL_aebc47bf8632.md`；
  版本记录在 `skills/maritime_commander/history/versions.jsonl`（含 old/new hash、
  evidence_refs、validation_result、rollback_target）。
- 历史 hash 记录：`e1f7839a…`（scale-gen 冻结旧版）。
- 无 git 历史（根目录非 git；hsystem git 不跟踪根 SKILL.md）。
- 当前 doctrine（`grep '^## '`）：Mission / Fair-play / Uncertainty semantics / UAV doctrine /
  Enemy UAV semantics / USV doctrine & engagement geometry / Local force concentration /
  Marginal overmatch / Low-confidence commitment / Maneuver detection / Endgame /
  Avoid overreaction / Commander role。

---

## 13. Skill-Update Closed-Loop Status

**RUNTIME 在线自更新：NO**（运行时永不 self-modify Skill；StrategicIntent 更新/Commander
intent 变化/V5 代码改动不属于 Skill update）。

**OFFLINE 可审计闭环：YES（已实现并演示一个具体闭环）**
- 实现：`skill_evolution.py`（管线）+ `skill_evolution_prompts.py`（三个外部结构化 prompt）
  + `skill_evolution_validate.py`（静态 Skill 审计 / 角色 schema）+ `test_skill_evolution.py`（35 项单测）。
- 闭环步骤（每步都有落盘证据在 `skill_evolution_runs/<evolution_id>/`）：
  1. **trigger**：确定性分类（`classify_evidence`）→ STRATEGIC_DOCTRINE + RECON，
     非 doctrine bug → `SKILL_CHANGE_NOT_JUSTIFIED`（停止，不怪罪 Skill）。
  2. **evidence**：`evidence.json`（真实 A→F 步证据，含 evidence_id，无 hidden truth）。
  3. **root cause**：manifest.classification.root_cause。
  4. **Analyst**（LLM 第 1 次）→ `analyst_output.json`（结构化，引用 EVID-xxx）。
  5. **Critic**（LLM 第 2 次，只见 Analyst 结构化输出，不见其 hidden state）→ `critic_output.json`。
  6. **Editor**（LLM 第 3 次，max 3 次调用）→ `editor_output.json`（MODIFY / NO_CHANGE）。
  7. **candidate diff**：`skill_before.md` / `skill_candidate.md` / `skill.diff` + old/new sha256。
  8. **validation**：schema + 现有单元/fair-play 测试（6 个文件）+ tiny regression（3 个 DEV 场景）。
  9. **approval**：默认 PENDING；显式 `--approve` → approval.json（approved_by=operator）。
  10. **release**：备份旧版 → 装入候选 → 写 versions.jsonl / release.json。
  11. **rollback**：`--rollback <hash-or-version>` 精确恢复旧文件（hash 校验）。
- 演示闭环：`evo_losttrack_coverage`（EVID-001 = run_ep4 step 336；Analyst→Critic→Editor；
  +2 行定性原则；static audit PASS；unit tests PASS；tiny regression PASS；approve/release v1；
  rollback target=aebc47bf…）。
- 仍未声称：held-out skill ablation、多版本统计比较、自动化放行。approval 必须人工显式执行。

---

## 14. LLM Self-Discussion Status

- **RUNTIME：NOT IMPLEMENTED**。当前 DeepSeek Commander = **single bounded strategic inference**
  （每触发一次调用一次，输出 StrategicIntent）。运行时无 analyst/critic/editor 讨论。
- **OFFLINE：YES，外部结构化 Analyst→Critic→Editor 仅**（`skill_evolution.py`）。
  三个角色为独立 LLM 调用、独立 context：Critic 只见 Analyst 的公开结构化输出，看不到其
  内部推理（prompt 明确禁止输出 CoT；only structured outputs）。演示中 Critic 实际拒绝了
  Analyst 的硬阈值建议（accept_analyst=false），Editor 采纳最小原则性改动——说明讨论有效。
- 无 hidden chain-of-thought 被请求或存储（`thinking disabled`；仅 text 块入档）。

---

## 15. What Is Already Defensible Tomorrow

1. 真实 runtime chain（HTTP-only Agent，无 engine import / 无 gRPC，白名单 API）。
2. Event-gated LLM（非每步调用；trigger 集、state-signature、no-change 滞回、last-valid
   fallback、policy clamp 均有代码路径与单测：test_v4/v5 覆盖 trigger/hysteresis/fallback）。
3. 静态 fair-play：runtime 零 black-truth 引用；audit_variable_cardinality 15/15、
   audit_scale_generalization 13/13；unit tests 49/41/37 全过。
4. 敌方运动学全在线推断（无固定速度/坐标/数量先验；首锁时间跨局稳定为几何不变量）。
5. OOB 裁判实验结论：全部 instrumented 局 enemy OOB=0（不虚高成绩）——有 CSV 证据。
6. Harness 极限（W5/W10）与 S10/S15 稳定性——有 CSV 证据。
7. Skill 为冻结文件、无在线更新（可声明"frozen versioned Skill"）。
8. **OFFLINE**：可声明"存在证据驱动的、可审计的离线 Skill 演化闭环（Analyst→Critic→Editor
   →diff→validation→approval→release→rollback）"，并有 1 个真实演示版本（v1）。

## 16. What Must NOT Be Claimed Tomorrow

1. **不得声称"任意 step_id 可回放 A→F"**（缺持久化与键关联，见 §5/§6）。
2. **不得声称"有 stale-response 防护"**（无 generation/version check，见 §4）。
3. **不得声称"有通信延迟/丢包模型"**（T3 NOT IMPLEMENTED；当前是 ideal shared sensing）。
4. **不得声称"有传感器噪声/延迟注入"**（T4 NOT IMPLEMENTED）。
5. **不得声称"在线自更新 Skill / 经过 held-out 统计验证的 Skill 更新"**——运行时 Skill 仍冻结；
   离线演化已实现（§13），但未做 held-out ablation、多版本统计比较、自动化放行。
6. **不得声称"运行时 LLM self-discussion / 多智能体反思"**——runtime Commander 仍为
   single bounded inference；仅**离线**存在外部结构化 Analyst→Critic→Editor（§14）。
7. **不得声称"能重建 Commander 精确输入/输出 payload"**（§5 C/D 未持久化）。
8. **不得把 StrategicIntent 更新 / Commander intent 变化 / V5 代码改动说成 Skill update**（§13）。
9. **不得把 TrackManager confidence 说成通信模型**（§10 T3）。
10. **不得把"集中式/共享感知"说成"中心全知"或"通信协议"**（§8.3）。

---

## 17. Minimum Fixes Before Review

### P0（最小可审计性）
1. **显式 step_id**：每个 decision round 一个单调递增 id，写进每步日志与 API 侧关联字段。
2. **Per-step manifest**：每步一行结构（step_id, sim_time, wall_time, trigger, source,
   intent, margin, action_count）。
3. **Raw /status（或白名单原始字段）落盘**：每步 dump 一次（JSONL）。
4. **Exact LLM request/response dump**：system/user 全文 + raw provider text（脱敏）+ latency。
5. **Applied action dump**：ActionSafety 过滤后实际 /apply 的 actions。

### P1（证据链完整）
6. **Fused-state dump**：每步 tracks（name/pos/conf/age/uncertainty/assigned）、resource ratios、
   clusters、mission。
7. **Allocator candidates dump**：top-k 候选价值 + best/second margin（已有 margin；补候选）。
8. **next-step feedback linking**：把上一 /apply 结果与下一 /status 观察用 step_id 关联。

### P2（鲁棒性/反泄漏）
9. **Stale-response 防护**：给 maybe_request 加 generation id，`_worker` 完成时校验仍是最新。
10. **Anti-leak 测试 T1（counterfactual）/ T2（truth-mask 断言）**：纯 unit test。
11. **通信/噪声模型**：若明日要声称模拟通信，需显式注入 delay/loss/noise（当前无）。

---

## 18. Three Evaluation Items

| 项 | 预计改动 | 风险 | 是否改变 policy semantics |
|---|---|---|---|
| A. Per-step A→F evidence bundle | medium | low | NO（纯 logging，不改决策路径） |
| B. Hidden-state counterfactual test | small（纯 unit test） | low | **YES**——可只写 unit test 不碰 Agent（构造 mock Obs：同一 white_observation、不同 hidden truth，断言 summary/allocator 输出一致） |
| C. Version/change matrix | small | low | **YES**——已有足够数据（报告中的 hash、SKILL_MD_SHA256.txt、各版本文件），可直接生成矩阵（但非单一机器可读 manifest） |

---

## 19. Verdict Summary

- RUNTIME CHAIN：VERIFIED（HTTP-only、无引擎 import、无 gRPC）。
- EXPLICIT STEP_ID：**NO**（CURRENT SYSTEM HAS NO EXPLICIT AUDITABLE STEP_ID）。
- ARBITRARY STEP A→F REPLAY：**FAIL**（B/C/D/E 未持久化、无键关联）。
- LLM：event-gated（非每步）；stale-response 防护 **NOT IMPLEMENTED**；last-valid intent 语义存在。
- TRUTH LEAKAGE（静态）：overall PASS；设计性 L4 身份、ideal shared sensing。
- ANTI-LEAK：T1/T3/T4 NOT IMPLEMENTED；T2 PARTIAL。
- SKILL：frozen、无在线更新；有 hash 历史无 git；无完整更新闭环；无 self-discussion。
