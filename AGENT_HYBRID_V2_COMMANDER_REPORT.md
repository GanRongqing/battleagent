# AGENT_HYBRID_V2 — LLM COMMANDER 评估报告

> 白方最终 Agent 第二版：`agent_hybrid_v2.py`（确定性核心 + Skill + 异步 LLM Commander）
> 评估日期：2026-08-10 ｜ 基线：`agent_hybrid_v1.py`（确定性，未修改）｜ 定位：可复现的架构验证 + 冒烟对比

---

## 1. 结论（TL;DR）

- **V2 在保留 V1 全部确定性控制能力的同时，接入了一个异步、非阻塞的 LLM Commander**：LLM 只输出战略级 `StrategicIntent`（姿态 / 火力集中度 / 预备队 / 威胁偏向 / UAV 模式 / 激进程度 / 优先级清单），**从不输出坐标级 move、锁定时序或合法动作**。
- **端到端验证局（LLM_ENABLED=true，含 UAV）通过**：对局结果 `Result.Victory`（敌方全歼 15/15），击杀 15、命中 24、我方 USV 损失 14、UAV 损失 2、突破 4。LLM 调用 34 次、解析失败 1 次、API 失败 0 次、平均延迟 1.8s 实况（≈90s 仿真等价）。
- **非阻塞性实测确认**：主循环每步（30 仿真秒）从未等待 LLM；后台线程 + 锁 + 快照摘要保证 Commander 返回即走。
- **公平性复核通过**：V2 依旧 HTTP-only，零 `black_*` 运行时读取、零引擎导入、零固定敌速/坐标/数量先验。唯一 `black_usv_states/vx=-10/BLACK_Y` 出现处是**自测的"禁止清单"断言**（证明摘要不含这些），符合规范。
- **Skill 已落地**：`skills/maritime_commander/SKILL.md` 只存长期稳定作战原则，无任何对黑方 script 的固定信息。
- **LLM_ENABLED=false 降级链路**：直接使用 DEFAULT_INTENT + V1 确定性核心，离线单测覆盖（不发起请求、保持默认意图）。

---

## 2. 目标与约束

优先级：跑通 → 不犯规 → 打完一整局 → 击杀敌舰 → 赢当前基线 → 泛化 → 代码简单。**不把已经能工作的确定性 Agent 变成一个脆弱的 LLM Agent**。

| 约束 | 落实 |
|---|---|
| 公平性铁律：禁止 `engine.black_*` / `get_state().black_*` / 固定敌初始坐标 / 固定敌数量 / 固定敌速度(如 vx=-10) / `black_strategy` / 直连引擎 gRPC | ✅ 运行时零读取，见 §4 |
| LLM 只做战略意图，**绝不做 raw controller**（obs→LLM→move/lock/fly） | ✅ §7：LLM 输出 schema 不含任何动作字符串 |
| TacticalSummarizer 不读取任何 black runtime truth | ✅ §6 + 自测断言 |
| LLM 绝对不阻塞实时控制 | ✅ §7 异步 + 单测 + 实测 |
| 同时间只允许一个 commander request in-flight | ✅ §7 单测覆盖 |
| 保留 V1 为 baseline，不破坏 v1 | ✅ v1 未修改（§3 基线说明） |
| LLM_ENABLED=false 必须完整运行（V1 确定性降级） | ✅ §8 单测 |
| 事件触发（first_detect / threat_spike / lost_high_threat / friendly_loss / multi_frozen / breakthrough_risk）带 cooldown | ✅ §7 实测 trigger 分布 |
| 参数化策略：focus / emergency / reserve / priority / uav_mode / 激进度 → 控制器联动 | ✅ §9 |
| 安全不变量保持硬编码：冻结不动作 / 死舰不动作 / lock 合法性 / 低电返航 / 机库冲突 / 已锁不切换 | ✅ 继承 V1 |

---

## 3. 架构总览

```
HTTP 观测(:8000 /status /legal_actions /apply)
   │
   ▼
TrackManager ──► 敌情航迹(仅观测推断)
   │
   ▼
TacticalSummarizer ──► 态势摘要(~1000-2000 tokens, 无 black truth)
   │                          │
   ▼                          ▼
LLM Commander(异步线程+锁)   StrategicIntent(默认 DEFAULT_INTENT)
   │  快照摘要, 绝不等待       │  clamp / 合法性过滤 / last-valid fallback
   ▼                          ▼
 最新 StrategicIntent ──► ThreatAllocator / USVController / UAVManager
   │                          │
   ▼                          ▼
ActionSafety(全动作 /legal_actions 校验) ──► /apply
```

| 模块 | 职责 |
|---|---|
| `TrackManager`（继承 V1） | 建航迹、常量速度外推、置信度衰减、尸体检测（>600s 静止） |
| `ThreatAllocator`（V2 参数化） | 威胁分 + 2v1/3v1 贪心；`intent` 调整 focus/emergency/reserve/bias/priority |
| `USVController`（继承 V1） | AVAILABLE/INTERCEPTING/LOCKING/FROZEN/DEAD 状态机 + 机会锁定 |
| `UAVManager`（V2 参数化） | 6 状态机 + 电量安全返航；`intent` 调整 search/reacquire 模式与优先级 |
| `SkillLoader` | 读取 `skills/maritime_commander/SKILL.md`（失败 fallback 内嵌 doctrine） |
| `TacticalSummarizer` | 每步构建观测纯态势摘要（含 CURRENT COMMANDER INTENT） |
| `LLMCommander` | `threading.Thread` + `Lock`；`maybe_request()` 立即返回；原子更新 `latest_intent` |
| `CommanderIntentAdapter` | 容错 JSON 解析 → 校验 → clamp → 删除失效 track → last-valid fallback |
| `AgentMain` | 主循环：status→obs→legal→track→alloc→usv→uav→safety→apply；触发检测 + 统计 |

**baseline 完整性**：`agent_hybrid_v1.py`（1154 行）自上一轮评估后**未被修改**，作为确定性对照基线保留。

---

## 4. 公平性复核（可复现）

```bash
# A. black_* 运行时引用（排除注释 / 奖励计数 / 自测禁止清单）
grep -nE "black_usv|black_uav|black_strategy|BLACK_Y|get_state\(\)\.black|\.black_" \
  agent_hybrid_v2.py | grep -vE "^\s*[0-9]+:\s*#|black_killed|black_hit|black_breakthrough"   # 仅自测断言行
# B. 硬编码敌速/敌坐标
grep -nE "vx\s*=\s*-10|\[-10|\bvelocity.*-10\b|BLACK_Y" agent_hybrid_v2.py                   # 仅自测断言行
# C. 引擎导入 / 直连 gRPC
grep -nE "import simulation|simulation\.core|simulation\.arsenal|tzb_engine|import base_server|import simserver" \
  agent_hybrid_v2.py                                                                            # 0 命中
```

- 对黑方的全部认知来自 `/status` 的 `white_observation`（雷达捕获/被动告警）与 reward 计数（`black_killed/black_hit/black_breakthrough`，均为允许的公共奖励信号），敌方运动学一律取自观测 `velocity` 在线推断。
- `agent_hybrid_v2.py:1719` 的 `forbidden` 清单是**正向自测**：断言摘要**不包含** `black_usv_states / black_uav_states / black_strategy / locked_times / vx=-10 / 260000 / BLACK_Y` —— 用于证明 TacticalSummarizer 干净，属合规用法。
- `SKILL.md` 内仅含通用平台规则与作战原则，无任何黑方 script 固定信息（详见 §5）。

---

## 5. 作战知识库 Skill（长期稳定 doctrine）

`skills/maritime_commander/SKILL.md` 全部内容都是**与具体敌 script 无关**的长期原则：

- **Fair-play doctrine**：明确列出 Commander 可用/禁止信息（只允许 friendly state / radar observation / TrackManager 航迹 / 已公开平台规则 / engagement state）。
- **USV doctrine**：雷达 35km、锁 <40km、单艇单锁、已锁不切换、300s 窗口独立 80% 命中、2 命中击沉、首命中冻结 300s → 推导 focus fire > 1v1、2v1 默认、紧急 3v1。
- **UAV doctrine**：60km ±30° 前向扇区、侦察非战斗、优先搜索未知区域 / 未交战威胁 / reacquire 高威胁 lost track；电量与返航由确定性 UAVManager 管理。
- **Information doctrine**：不识别 script 名称，按 position/velocity/confidence/threat/集中度/航向变化 判断态势；敌方行为变化 → 通过新观测调整 intent，不切换固定模板。
- **Resource doctrine**：敌情不完整时保持 reserve 与搜索能力；临近突破高威胁时可降 reserve 增 attacker。
- **Commander role**：只输出战略级 intent，禁止坐标级 move / 合法动作串 / 单艇航路 / 管理 UAV 电量 / 重复 simulator 自动维护的 lock timing。

---

## 6. TacticalSummarizer（态势摘要）

每步由观测纯数据构建，输出 `(text, [track_names])`。格式固定（让 LLM 稳定解析）：

```
TIME: ... | MISSION: 阻止敌方USV突破 | FRIENDLY: USV x/y (含 frozen/locking/dead) | UAV x 飞行/返航
KNOWN ENEMY TRACKS: <name>(x,y,vx,vy,conf,age) ...   # 仅来自观测
TOP THREATS: <name>(score,dist,conf) ...
ENGAGEMENT: 正在锁定 <target> 的 USV 列表 / 冻结情况
RECON: UAV 当前模式与重点
CURRENT COMMANDER INTENT: posture/focus/...          # 当前生效意图
```

- **零 black truth**：只消费 `Obs`（/status 解析）与 TrackManager 内部航迹，所有字段来自雷达捕获/被动告警。自测断言 `black_usv_states/vx=-10/BLACK_Y` 不在摘要中。
- **规模控制**：只列 top-N 航迹与 top-3 威胁，保持 1000-2000 tokens 量级。
- 返回的 `track_names` 是**当前有效航迹**，供 CommanderIntentAdapter 过滤 LLM 的 priority_tracks。

---

## 7. LLM Commander（异步非阻塞指挥）

### 7.1 调用与网络

- 复用 `agent_llm.py` 验证过的 DeepSeek/Anthropic 兼容调用：`ANTHROPIC_BASE_URL / ANTHROPIC_AUTH_TOKEN / ANTHROPIC_MODEL` 环境变量，无硬编码密钥，`thinking: disabled`。
- 提示词 = `Skill 全文`（system）+ 摘要 + `INTENT_SCHEMA_DOC`（结构化输出说明）+ "只输出 JSON，禁止动作字符串" 约束。
- `COMMANDER_TIMEOUT_S`（默认 12s）内无响应 → 记 `api_failure`，保留 last valid intent。

### 7.2 异步模型（实测非阻塞）

```python
def maybe_request(self, now_sim, summary_text, valid_tracks, trigger):
    with self.lock:
        if self._disabled or now_sim < self.last_request_sim + COOLDOWN: return
        if self.in_flight: return                       # 同时间仅 1 个 in-flight
        self.in_flight = True
        self.last_request_sim = now_sim
        self._spawn_worker(summary_text, valid_tracks, trigger)   # 立即返回

def get_intent(self):
    with self.lock: return self.latest_intent           # 主循环原子读取
```

- 主线程 **永不等 LLM**；后台 worker 解析成功后 `with self.lock: self.latest_intent = parsed`。
- 单测实测：`maybe_request` 在 0.00s 内返回；in_flight 期间第二个请求不启动；worker 完成后意图原子更新。
- **实测验证**（对局日志）：主循环每 30 仿真秒推进，Commander 请求异步触发，未见任何等待；实况延迟 1.8s ≈ 仿真 90s，在 600s cooldown 内自然完成，主循环完全无感。

### 7.3 触发与 cooldown

- `MIN_COMMANDER_INTERVAL_SIM = 600`；请求间距实测 ≈600s。
- 事件触发器（优先级从高到低）：`breakthrough_risk`（任何航迹 x<90km）、`multi_frozen`（≥3 艘冻结）、`friendly_loss`（USV 数下降）、`lost_high_threat`、`threat_spike`（可见敌 +3）、`first_detect`、`periodic`。
- 验证局 trigger 分布：`periodic 18`、`lost_high_threat 10`、`breakthrough_risk 7`。事件触发正常覆盖周期节奏。
- **已知行为（非 bug）**：`first_detect` 在验证局被 cooldown 掩蔽（t=1546 首次探测，但上一次请求 t=1213，未过 600s）——periodic 请求已覆盖初始态势，按规范事件同样受 cooldown 约束。

### 7.4 统计

`commander.stats = {calls, parse_failures, api_failures, latency_sum, ...}`，随每局 `[META]` 输出，供对比报告使用。

---

## 8. StrategicIntent + CommanderIntentAdapter

### 8.1 意图结构（`__slots__` 紧凑类）

```python
posture='balanced'            # balanced/aggressive/defensive
focus_level=2                 # 钳制 1..3
emergency_focus_level=3       # 钳制 2..4
reserve_usvs=3                # 钳制 0..8
threat_bias='breakthrough_eta'# breakthrough_eta/highest_confidence/nearest
uav_mode='search_and_reacquire'  # search_and_reacquire/broad_search/focus_fire
uav_priority_tracks=[], priority_tracks=[]
recon_aggressiveness=0.6      # 0..1
engagement_aggressiveness=0.7 # 0..1
```

`DEFAULT_INTENT` 与规范完全一致。任一字段非法 → 回退默认值。

### 8.2 适配器安全网

- **容错 JSON 解析**：容忍 markdown 围栏、前后缀文本；`extract_json_object` 用括号平衡扫描器找最外层 JSON。
- **校验/钳制**：POSTURES / BIASES / UAV_MODES 白名单集合；数值 clamp（focus 1-3、emergency 2-4、reserve 0-8、recon/engage 0-1）。
- **删除不存在航迹**：`priority_tracks` / `uav_priority_tracks` 对照摘要返回的 `valid_tracks` 过滤，删除已失效/不存在的 track。
- **last-valid fallback**：解析失败（非 JSON / 损坏 JSON / schema 越界）→ 保持上一份有效意图，不降级为"无指挥"；记录 `parse_failure`。
- 单测覆盖：正常 parse、非 JSON fallback、markdown+损坏 fallback、clamp、无效 track 删除。

---

## 9. 参数化策略（intent → 确定性控制器联动）

| intent 字段 | 确定性联动 | 安全不变量（硬编码，不受 intent 影响） |
|---|---|---|
| `focus_level` | 每目标最大 attacker 数（`desired_attackers`） | 冻结单位不发动作、死舰不发动作 |
| `emergency_focus_level` | 紧急高威胁（x<`emg_x`）集中度 | lock 合法性（不可见/越程不锁） |
| `reserve_usvs` | 非紧急期从分配中保留的可用 USV 数 | 低电 UAV 强制返航 |
| `threat_bias` | 威胁分权重：breakthrough_eta(1.9×近距) / highest_confidence(1.8×置信) / nearest(近距加成) | 机库冲突、已锁目标不切换 |
| `priority_tracks` | 对分配排序加轻微分数加成 | 2 命中击沉 / 300s 结算由引擎维护 |
| `uav_mode` | 搜索/重搜/扇区策略分配 | 世界边界巡逻界、电量安全返航 |
| `recon_aggressiveness` | 搜索与重搜 UAV 数量/半径加权 | — |
| `engagement_aggressiveness` | `emg_x = EMERGENCY_3V1_X × (0.5+agg)`（越积极越早 3v1） | — |

- **实例（验证局 t=19167）**：仅剩 1 艘 USV 且黑方 2 舰逼近 → LLM 返回 `posture=aggressive focus=3 emergency=4 reserve=0`（全火力投入、零预备队），确定性核心据此将所有可用资产压向突破线目标。观测到的每条 intent 均被正确 clamp 与 apply。

---

## 10. 冒烟评估与对比（V1 vs V2）

### 10.1 离线测试

| 测试 | 结果 |
|---|---|
| `selftest_trackmanager`（7 项，含尸体检测） | ✅ 全部通过 |
| `mocktest_commander`（8 组 / 19 项：Skill 读取、摘要无 black truth、JSON 解析、malformed fallback、clamp focus=10、无效 track 删除、timeout 非阻塞、LLM_ENABLED=false 降级） | ✅ 全部通过 |
| LLM_ENABLED=false 完整运行路径 | ✅ 单测：不发起请求、保持 DEFAULT_INTENT；运行时等同 V1 确定性核心 |

### 10.2 端到端验证局（V2，LLM_ENABLED=true）

| 指标 | 值 |
|---|---|
| 对局结果（/result 权威） | `Result.Victory`（敌方全歼） |
| 击杀 / 命中 / 突破 | 15 / 24 / 4 |
| 我方 USV 损失 / UAV 损失 | 14 / 2 |
| first_detection / first_lock | 1546s / 7365s |
| LLM calls / parse_failures / api_failures | 34 / 1 / 0 |
| LLM 平均延迟 | 1.8s（实况）≈ 90s 仿真等价 |
| trigger 分布 | periodic 18 / lost_high_threat 10 / breakthrough_risk 7 |

> 注意：本局是我方险胜（突破 4 但全歼），与 V1 报告 §6 中"胜局突破 3-7"的形态一致 —— 对杀竞速仍受引擎 RNG 方差主导，5 局冒烟仅作 smoke，不夸大统计意义。
>
> **修复记录**：验证局首跑时 `[META] result` 误报 `Defeat`（引擎在 Agent 最后一步 /status 里因击杀计数滞后、`black_ship_alive` 未及翻 0 而临时判定"突破 Defeat"）。已改为以 `/result` 权威判定为准（`_print_meta` 接收 `final_result`），后续冒烟 5 局 META 与终局一致（R2-R4 均正确报 Victory）。

### 10.3 V1 vs V2 冒烟对比（各 5 局）

> 引擎实际速率约 13-40×（目标 50×，CPU 受限）；每局 6-8 分钟。V2 = `LLM_ENABLED=true`；V1 = 确定性基线（v1 未修改）。**冒烟仅 5 局，结论不夸大统计意义。**

**V2（LLM Commander，已完成 5/5）**

| 局 | 结果 | victory_time | friendly_losses | enemy_kills | first_det | first_lock | LLM calls | parse_fail | avg_latency |
|---|---|---|---|---|---|---|---|---|---|
| R1 | **Defeat** | 15027 | 15 | 11 | 1569 | 7386 | 22 | 0 | 1.8s |
| R2 | **Victory** | 21577 | 13 | 15 | 1549 | 7395 | 34 | 0 | 1.8s |
| R3 | **Victory** | 21007 | 14 | 15 | 1559 | 7379 | 34 | 0 | 1.7s |
| R4 | **Victory** | 21181 | 12 | 15 | 1577 | 7414 | 34 | 0 | 1.6s |
| R5 | **Defeat** | 18980 | 15 | 12 | 1553 | 7385 | 31 | 0 | 1.7s |

- V2 冒烟：**3 胜 2 负（60%）**；所有胜局均为全歼（15/15），两场负局均为"对杀竞速 RNG 崩盘"（我方全灭、击杀 11-12）——与 V1 的失败形态完全一致。
- 冒烟 5 局 **LLM 解析失败 0 次、API 失败 0 次**；请求量 22-34 次/局，与 600s cooldown 理论上限吻合。
- 平均 LLM 延迟 1.6-1.8s 实况 ≈ 80-90s 仿真等价，在主循环 30s 步长与 600s cooldown 内完全无感（非阻塞）。

**V1（确定性基线，已完成 5/5）**

| 局 | 结果 | kills | USV损失 | UAV损失 | 突破 | 时长 |
|---|---|---|---|---|---|---|
| R1 | **Victory** | 15 | 14 | 3 | 1 | 1090s |
| R2 | **Defeat** | 15 | 15 | 15 | 2 | 1046s |
| R3 | **Victory** | 15 | 15 | 2 | 1 | 1067s |
| R4 | **Defeat** | 11 | 15 | 15 | 0 | 725s |
| R5 | **Defeat** | 15 | 15 | 15 | 1 | 802s |

### 10.4 对比汇总

| 指标 | V1（确定性） | V2（LLM Commander） |
|---|---|---|
| 胜率 | **2/5 = 40%** | **3/5 = 60%** |
| 平均击杀 | 14.2 | 13.6 |
| 平均 USV 损失 | 14.8 | 13.8 |
| 平均 UAV 损失 | 10.0 | 2.0 |
| 平均突破 | 1.0 | 0.8 |
| first_detection（均值） | 未记录 | 1561s |
| first_lock（均值） | 未记录 | 7392s |
| LLM calls / parse_failures / avg_latency | — | 31 / 0 / 1.72s |

**解读（谨慎，5 局 smoke 不夸大统计意义）**：

1. **双方负局形态完全一致**——都是"对杀竞速 RNG 崩盘"（我方全灭、击杀 11-15、突破 0-2），与 V1 报告 §7 的结论相同：这是引擎对称 15v15 的方差，观测纯解法内无干净修复。
2. **V2 胜局均全歼（15/15）且存活 ≥1 USV**；V1 有两局"我全歼敌但己方同归于尽"被判 Defeat（R2/R5，引擎判"我方所有单位被击毁"优先）。这是本 5 局样本里 V1 多输 1 局的直接来源，样本噪声占主导。
3. **LLM 层没有拖累确定性核心**：LLM 平均延迟 1.72s（≈86s 仿真等价），在 600s cooldown 内完全无感；5 局解析失败 0、API 失败 0；请求 22-34 次/局，cooldown 节奏与设计一致。
4. **结论范围**：V2 在"不破坏已工作的确定性 Agent"前提下接入了异步战略层，冒烟表现不劣于（且略优于）V1 baseline。真正要说 V2 显著更强，需要更多对局，不在本 5 局 smoke 的声明范围内。

（冒烟结果见 `/tmp/smoke_results.txt`（V1）与 `/tmp/smoke_v2_results.txt`（V2）。）

---

## 11. 未实现 / 后续方向

- `first_detect` 事件在 cooldown 窗口内被掩蔽（行为已记录，规范允许，不改）。
- 未做：LLM 动态调节具体单艇分配（明确禁止）、基于 RL 的参数寻优、对手行为聚类、影响图。
- 后续可扩展：事件触发绕过一次 cooldown（如需更即时响应）；把 `[META]` 与 `run_smoke_v2.sh` 的解析字段扩展为正式评估管道。

---

## 12. 复现方式

```bash
# 1) 启动 POMDP API 服务器 (端口 8000) + 仿真后端
# 2) 离线测试
/root/miniconda3/envs/hsystem_env/bin/python -c "import agent_hybrid_v2 as a; a.selftest_trackmanager(); a.mocktest_commander()"
# 3) 冒烟评估: V1 与 V2 各 N 局
bash run_smoke.sh 5                    # V1 确定性基线 → /tmp/smoke_results.txt
bash run_smoke_v2.sh 5                 # V2 LLM Commander → /tmp/smoke_v2_results.txt
# 4) 单局(带 UAV + LLM)手动验证
LLM_ENABLED=true /root/miniconda3/envs/hsystem_env/bin/python agent_hybrid_v2.py --uavs
```
