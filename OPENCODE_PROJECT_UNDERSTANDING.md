# OpenCode Project Understanding

> 项目：POMDP 海上无人集群对抗（hsystem）
> 阶段：第一阶段 complete repo reconnaissance（只读，不修改任何代码）
> 日期：2026-08-13
>
> 资料来源优先级：`CURRENT CODE > CURRENT CONFIG > LOGS/DATA > REPORT`。
> 本文件中的所有**事实**均来自源码 / 当前配置 / CSV / 日志；**推断**一律显式标注 `[推断]`。
> 报告仅用于建立背景，凡与代码冲突处以代码为准，冲突已在对应小节标注。

---

## 1. Executive Summary

这是一个 **对抗仿真博弈任务**：白方（我方，由 Agent 控制）用 USV + UAV 编队在任务区域内迎战黑方（敌方，由固定脚本控制）USV + UAV 编队。

- **胜负**：黑方全部 USV 被击毁 → 白方 Victory；白方全部单位（USV+UAV）被击毁 → Defeat；任一黑 USV 突破 x≤50000m → Defeat。
- **为何是 POMDP**：白方己方状态完全可观（/status 白名单），但敌方状态**只来自探测**（雷达捕获 = 真实坐标+速度，被动告警 = 仅方位），目标离开传感器后有 30s 情报黏性，随后从观测中消失。敌方数量/位置/速度必须**在线推断**。
- **系统架构**：Agent → HTTP :8000（pomdp_api）→ gRPC → base_server :6000 → sim_server :6001 → 仿真引擎。引擎以 50× 实时在后台线程持续运行、**从不等待 Agent**。
- **平台核心机制**：2 次命中击沉；每次锁定 300s 窗口 80% 命中；第 1 发命中冻结 300s；锁距 <40km；USV 20 m/s / UAV 150 m/s（/fly schema 上限 100，可执行上限 100）；UAV 60km±30° 前向扇区雷达；UAV 探测全舰队共享。
- **Agent 现状**：V1 = 确定性（无 LLM）；V2 = 确定性执行核 + 异步 LLM Commander（只输出战略意图 StrategicIntent）。V2 是当前正式 Agent。
- **40 局规模泛化实验（10/15/20/30v10）**：报告胜率 30%/60%/40%/30%（总 40%）。
- **本侦察最重要的新发现**：20v20/30v30 的若干"胜利"其实是**引擎结束顺序 quirk**（最后一艘黑舰突破瞬间被裁判击杀 → `black_ship_alive==0` 先于 `black_breakthrough>0` 判定 → Victory）。若剔除这些 quirk 胜利，**干净击杀竞速胜率约为 10v10=30%、15v15=60%、20v20=30%、30v30=0%**（30v30 的 3 场"胜利"全部靠 quirk）。
- **10v10 失败模式**：5v5 对称对杀竞速（纯 RNG），白方 USV 全灭时往往还有 1–2 艘黑舰存活；而白方 UAV 在 USV 全灭后因"无回收舰 + RTB 逻辑把全部 UAV 逼入 RETURN"继续向西飞，**飞出西边界 x<0 被裁判击毁**，最终触发"我方所有单位被击毁"→ Defeat。UAV 西飞出界是败局 UAV 全灭的真实原因（报告将其误记为"基地被突破端冲毁"）。
- **随机路径 (random waypoint) 首要风险**：TrackManager 只有**点估计 + 常量速度外推**，敌方一旦转向，预测误差无界增长、无 uncertainty region；UAV reacquire 是"飞向单一预测点"，搜索策略只覆盖东西条带（140–260km），对转向目标鲁棒性差。

---

## 2. Repository Map

```
/root/autodl-tmp/hsystem/                          # 项目根（非 git 仓库）
├── agent_hybrid_v1.py                             # 白方 Agent V1（确定性，无 LLM）1154 行
├── agent_hybrid_v2.py                             # 白方 Agent V2（确定性核 + LLM Commander）1963 行
├── agent_llm.py                                   # 早期纯 LLM agent（每步调 LLM，30v30 不可行）
├── agent_attack.py / agent_defense.py / agent_win.py
│     / agent_recon.py / agent_test.py             # 历史变体（含 BLACK_Y 硬编码作弊，已弃用）
├── skills/maritime_commander/SKILL.md             # Commander 长期作战知识（sha256 已冻结）
├── SKILL_MD_SHA256.txt                            # 冻结的 Skill hash（与当前文件一致）
├── run_smoke.sh / run_smoke_v2.sh                 # V1 / V2 冒烟评估脚本
├── run_scale_eval.py                              # 40 局规模泛化评估 runner
├── audit_scale_generalization.py                  # 规模耦合审计（13/13 PASS）
├── scale_generalization_results.csv               # 40 局逐局数据
├── scale_generalization_aggregate.txt             # 聚合表
├── *.md                                           # 6 份报告（V1/V2/scale/platform/rules/recon）
├── probe_rules/*.py                               # 机制探测脚本（短时，引擎只读）
├── config_backup/                                 # 早期"打赢配置"备份（含作弊坐标）
├── logs/scale_scenario_*_game*.log                # 40 局完整 agent 日志
├── Mwork/                                         # 早期仿真输出数据
└── hsystem/                                       # 仿真系统（独立 git 仓库，含 .git）
    ├── pomdp_api/main.py                          # HTTP :8000 → gRPC 网关（1881 行）
    ├── pomdp_api/api_logs/                        # 运行日志 + 对局 JSON 日志
    ├── simserver/
    │   ├── base_server.py                         # gRPC :6000 网关（路由到 sim_server）
    │   ├── sim_server.py                          # gRPC :6001，加载脚本→引擎→后台线程
    │   ├── config/sces.json                       # 场景注册（测试用例1 + 4 个规模场景）
    │   └── simserver.proto / _pb2*.py             # gRPC 协议
    ├── sim_script/20250819TZB/
    │   ├── sim_20250819测试用例1.py               # 原始 30v30（15+15）黑方脚本
    │   ├── scenario_builder.py                    # 参数化场景构建器（build_scenario）
    │   ├── scenario_10v10/15v15/20v20/30v30.py    # 4 个薄 wrapper（只传数量）
    │   └── Demo/任务区域.json                     # 任务区域多边形
    └── simulation/                                # 仿真引擎（Cython 编译 .so/.pyd）
        ├── core/{engine,tzb_engine,base_engine,arch,entity,...}.pyx/.back
        ├── arsenal/{locker,motor,tzb_motor,radar,intelligence,platform,uavbattery,judge_system,...}.py
        └── database/json/*.json + cache_*.pkl     # 运行时 DB（cache pkl 与磁盘 json 不一致）
```

**注意**：Agent 代码在根目录（不在 hsystem git 仓库内）；hsystem/ 是仿真系统的独立 git 仓库（提交历史 2025-09 起，含 .idea/build 等删除状态）。

---

## 3. Simulator Runtime Architecture

### 3.1 完整运行链路（已从代码验证）

```
White Agent (agent_hybrid_v1/v2.py)
      │  HTTP :8000  (requests, JSON)
      ▼
pomdp_api/main.py  ──FastAPI 网关──  /start /status /obs /legal_actions /apply /result /stop /reset ...
      │  gRPC (:6000, flag="simulation")
      ▼
simserver/base_server.py  control()  → 按 flag=="simulation" 路由
      │  查询 free client (SimClient) → push_req
      ▼  gRPC
simserver/sim_server.py  :6001
      │  init(): 读 sces.json → 写 temp.py → import temp → temp.sim(**kwargs)
      │          → engine.activate()  →  threading.Thread(target=engine.update) 后台常跑
      ▼
simulation/core/engine.update()  (base_engine)  仿真引擎持续推进
```

各服务启动文件：
- `pomdp_api/main.py`：`uvicorn` 监听 `0.0.0.0:8000`（`APP_PORT` 环境变量可改）。
- `base_server.py`：gRPC `:6000`（本机启动需设 `SIM_HOST=127.0.0.1`）。
- `sim_server.py`：gRPC `:6001`，启动时向 base_server 注册。
- 三个服务通过 `sces.json`（场景注册表）协同。

### 3.2 时间推进机制（关键）

- **引擎持续运行、永不等待 Agent**：`engine.update()` 是一个后台线程的实时时钟循环（`engine.py.back:968-1073`），以 `_upper_tick = begin_sim_tick + (now_real - begin_real) * ratio` 控制推进。`ratio=50`（场景 `set_ratio(50)`），实测约 48–51×（由 CSV wall/sim 比例推断）。
- **`/apply` 不是引擎门控**：`/apply` 只执行动作并设置 `release_until_time = current + MACRO_STEP(30)`（`main.py:1781`）。引擎本身不检查该值（`waiting_for_command` 只是只读提示）。真正决定"每步推进多少仿真秒"的是 **Agent 决策循环的墙钟耗时 × ratio**。
- **Agent 步进节奏**：V1/V2 每步 `status → legal → track/alloc → usv/uav → apply → sleep(0.05s)`。在 ratio≈50 下每步约推进 20–30 仿真秒。`MACRO_STEP_DURATION=30`（名义宏观步长）。
- **simulation time 与 wall-clock**：`局内时间`（HH:MM:SS）由 `episode_elapsed = engine.time - start_sim_time` 计算（`main.py:1582`）；第一帧检测 ~1545s、第一锁 ~7355s 等与几何计算吻合（见 §5/§6）。
- **reset/start/result**：
  - `/start?script_name=`：`_do_init` → `_grpc_call("terminate")` 清残留 → `init`（写 temp.py + activate + 后台线程）→ 重置 `_state` → 校准 epoch。
  - `/reset?script_name=`：封存上局日志 → 终止 ×2 → `_do_init` → 重置（episode_id=1）。
  - `/stop`：先取最终状态封存日志 → `terminate`。
  - `/result`：取最新 raw → `_build_result`（判定见 §6）。
- **对局日志**：每步写入 `api_logs/games/game_<episode>_<ts>.json`（StepRecord：动作/结果/USV/UAV/敌情/奖励/事件），结束封存。

---

## 4. POMDP Observation & Action Interface

### 4.1 Endpoints（`main.py` 全部端点）

| Endpoint | 输入 | 输出 | 数据来源 | Agent 可访问 |
|---|---|---|---|---|
| `GET /` | – | 服务说明/端点清单/状态 | `_state` | ✓ |
| `GET /health` | – | gRPC 连通/引擎状态 | gRPC | ✓（运维） |
| `GET /scripts` | – | `AVAILABLE_SCRIPTS` 列表 | 常量 | ✓ |
| `POST /start?script_name=` | script_name | 对局编号/状态 | `_do_init` | ✓ |
| `GET /stop` | – | 停止+封存日志 | – | ✓ |
| `POST /reset?script_name=` | script_name | 重置结果 | – | ✓ |
| `GET /status` | – | **结构化资源快照**（统计/单位状态/观察信息/奖励信号/局内时间/已结束/行动历史） | `_fetch_raw_state` + 白名单过滤 | ✓（Agent 主数据源） |
| `GET /obs` | – | **Plain Text 语义观测**（[Info]/[我方无人艇]/[我方无人机]/[敌方情报]/[派生信号]） | 同上 | ✓（LLM/展示） |
| `GET /legal_actions` | – | 5 组动作 + 备注 + 被动告警建议 | 同上 | ✓（动作掩码权威） |
| `POST /apply` | `{actions:[{action_text,action_type}]}` | 逐条执行结果/跳过/统计 | `_execute_one_action` | ✓ |
| `GET /result` | – | 对局结果/结果说明/存活统计/奖励/行动历史 | `_build_result` | ✓（权威结果） |
| `GET /game_log` | – | 当前对局完整 JSON 日志 | `_game_log` | ✓（分析用） |

### 4.2 Friendly full state（白方可看到，`/status` 白名单，`main.py:1605-1624`）

- **USV（white_usv_states）**：`name / is_alive / position / velocity / course / speed / is_locked / is_locking / is_frozen / locked_attacker / relative_orientation / locking_unit / locked_times / uav(机库无人机名)`。
- **UAV（white_uav_states）**：`name / is_alive / position / velocity / course / speed / battery / battery_format / is_charging / is_at_usv / home_name`。
- **统计**：`usv_total / usv_alive / uav_total / uav_alive / uav_flying / enemy_visible`（`enemy_visible = len(active)+len(passive)`，是"可见敌"计数，**不是**敌方总量）。
- 白方全部状态为**真值**（己方完全可观）。

### 4.3 Enemy active observation（`white_observation`，`_build_enemy_intel` main.py:650-698）

- **`active`（[雷达捕获]）**：`{name, position, velocity}` —— 来自 `engine.get_white_targets()`（`engine.py:246-272`）= **所有 RED 单位 intel.targets 的并集**（全局共享感知）+ **BLUE Ship 中 `locker.locked or locker.frozen`**。内容是**真实坐标/速度**（确定性探测，无噪声）。
- **`passive`（[被动告警]）**：`{name, bearing, detected_by}` —— 从白方 USV/UAV 的 `locked_attacker`（攻击者名）+ `relative_orientation`（方位角）生成。**只有方位、无坐标**。攻击者名来自 `emy_name` 列表（L5：该列表只增不删 → 存在"幽灵被锁"）。

### 4.4 Lost target behavior（TrackManager 视角 + 引擎事实）

- 引擎侧：雷达轨迹 2s 过期（`radar.pyx`），intel 轨迹 **30s 情报黏性**后过期（`intelligence.py` `radar_update_time=30`）。
- **锁住/冻结的敌舰永久可见**（`engine.py:257-264`）—— 一旦有白 USV 锁住它，即使雷达失效，它也会以**真实坐标**持续出现在 `/obs`，直到被击沉。击沉后因 `locker.locked` 永不复位（quirk）→ **尸体永久残留**。
- Agent 端 TrackManager：保留航迹直到 `age >= DROP_AGE(180s)`；30s 内高置信、30–120s 估计置信、>180s 丢弃。丢失后用**常量速度外推**（`predicted_position`）。
- `kill_detect` 用两个证据：A) `black_killed` 奖励增量 + engaged 消失名单；B) **尸体检测**（位置持续 >600s 不变 = 尸体，含"被锁尸体永久残留 intel"）。

### 4.5 黑方信息在 API 层是否可见（已确认）

- `tzb_engine.get_state`（`tzb_engine.py:20-149`）的 raw 里**确实含** `num_black_usv/num_black_uav`、`black_usv_states`（仅 name/is_alive/is_frozen/locked_times，**无坐标**）、`black_uav_states`（含动力学）。
- **但 pomdp_api `/status` 只白名单转发白方字段**，`black_*`/`num_black_*` 一律不透出（grep 确认 `main.py` 无任何 `black_usv_states`/`num_black` 引用）。
- 白方唯一可见的黑方信息 = `white_observation`（观测） + `奖励信号`（`black_killed/black_hit/black_breakthrough/white_*`，均为**累计奖励计数**）。

---

## 5. Platform Mechanics

以下均来自源码 / 探测报告 / 日志，重点标注与旧报告的冲突。

### 5.1 USV（Ship / MotorTZB / RadarWithGuider）

| 项 | 值 | 依据 |
|---|---|---|
| 最大速度 | **20 m/s**（引擎运行时 DB cache_json.pkl；`motor.json` 写 10 但未被加载） | PLATFORM_CAPABILITIES §修正2；probe_cap_speed |
| 加速度 | 2 m/s² | motor.json / tzb_motor.py |
| 转向 | **近似瞬时**（实测 ≤0.15s） | probe_cap_turn8/9；PLATFORM_CAPABILITIES §修正1 |
| 指令 | `move target_speed∈[0,100](引擎钳到20) target_course∈[0,360]`，持久生效 | `_ACTION_SCHEMAS` / `send_command` |
| 雷达 | **35km 全向**，探测 `fixed`（确定性无噪声），周期 2s | 场景 L71-73 |
| 锁距 | **<40km**（`distance < 40000`；断链 `>=40000`） | `engine.py:303` / `locker.py:98,155` |
| 机库 | 每 USV 最多 1 架 UAV；可跨母船降落 | `platform.py:89-94` |

### 5.2 Lock / Combat（`arsenal/locker.py`，最核心）

- 建链：`cmd_lock`（`engine.py:285-320`）：攻击者/目标均 Ship、异阵营、攻击者必须 RED、目标须在 `white_targets`、距离 <40km、**一船一锁不可切换**（`attacker.locker.is_locking`）。
- 计时在**目标侧 locker** 自主运行（`_locked_work` 每 1s），与 Agent 是否重复发锁无关。
- **300s 窗口**（`locked_time > 300`）结算：`random.random() > 0.2` → 80% 命中。命中则 `locked_times+=1; frozen=True`（冻结 300s）；无论命中与否，窗口结束即释放该攻击者。
- **累计 2 次命中击沉**（`sum(locked_times)>=2` → `home_unit.kill()`，连带机载 UAV 死亡）。
- **冻结 300s**：停船+雷达关+locker 关，300s 自动解冻。
- 多 USV 可同时锁同一目标（独立链）；2v1 理论 300s 击杀 64% / 600s 累计 93%；1v1 期望 ~600-975s；3v1 300s ~90%。
- **锁断条件**：距离 ≥40km；目标沉没；窗口到期自动释放。
- **锁不依赖雷达**：目标被锁后永久在白方情报里（`engine.py:257-264`），UAV 失去目标后既有锁链继续推进。
- **corpse quirk**：击沉后 `locker.locked` 不复位（`_locked_work` 在 kill 处 `return`，未走到 `self.locked=False`），尸体以固定坐标+陈旧速度永久留在 intel。
- **命中后锁链不因攻击者死亡而失效**（`_locked_work` 只查距离和窗口，攻击者死亡后仍按原位置距离结算）→ 白方 USV 全灭后仍可能补刀成功（10v10 胜局最后一杀即由此产生）。

### 5.3 UAV（AEW / PlaneMotorTZB / UavBattery / RadarWithGuider）

| 项 | 值 | 依据 |
|---|---|---|
| 最大速度 | **150 m/s**（场景覆盖）；**但 `/fly` schema 上限 100 → 可执行上限 100** | 场景 L90；`_ACTION_SCHEMAS.fly` |
| 加速度 | 10 m/s² | motor.json |
| 雷达 | **60km ±30° 前向楔形，锚定航向**（悬停则扇区冻结在最后航向，必须飞行才能扫描） | 场景 L87-89；radar.pyx |
| 电池 | 总飞行 25000s 线性消耗，**<0 即死、无自动返航**；充电 1.389 飞行秒/秒，必须在机 | uavbattery.py |
| 起飞 | UAV ∈ 母船机库 | `cmd_uav_takeoff` |
| 降落 | 任意同阵营存活 USV 均可接收（跨母船合法）；条件 `dist<10km 且 speed<100`；API 对 >5m 自动以 speed=50 制导 | `cmd_uav_land` / `main.py:1149-1170` |
| 母船被击沉 | 机载 UAV 连带死亡 | locker.py:114-118 |
| 战力 | **不能锁定/不能击杀**（无 locker；cmd_lock 要求目标为 Ship） | engine.py |

### 5.4 Shared sensing（传感器辅助首锁战术窗口）

```
UAV 60km 前向探测
   ↓ intel.targets（全局并集）
get_white_targets()  ← 任意白 USV 可见并可锁（需 <40km）
   ↓
白 USV 可在自身 35km 雷达之外、40km 锁距之内锁定目标（35km<40km ⇒ 无锁隙）
```
- 验证（probe）：白 USV 在 38.6km（>35km 雷达）锁黑船成功；黑方 UAV 同样给黑 USV 延长锁距。
- **35–40km 区间 = UAV 辅助的"先于自身雷达"锁定窗口**，是 UAV 的核心战术价值。
- 情报过期 30s（目标脱离雷达后仍可新锁，超过则无既有锁时新锁失败）。

---

## 6. Victory / Defeat Rules

### 6.1 判定顺序（`tzb_engine.py:120-135`，顺序即优先级）

```python
if total_white_alive == 0:          # 白方 USV + UAV 全灭
    → "我方所有单位被击毁" → Defeat
elif black_ship_alive == 0:         # 黑方 USV 全灭
    → "敌方所有单位被击毁" → Victory
elif black_breakthrough > 0:        # 任一黑 USV x≤50000
    → "敌方N艘艇突破防线" → Defeat
elif not isactive:                  # end_time=600000s
    → "仿真引擎已停止"
```

- **正常胜利唯一途径**：在首个黑舰突防前把黑 USV 全部击毁。
- 突防判定：`judge_system._judge`（每 1s）：黑 USV `coords[0] <= 50000` → 记 `black_success`、`unit.kill()`。
- **quirk（已实测）**：若**最后一艘**黑舰突防并被裁判 kill()，`black_ship_alive==0` 在 `black_breakthrough>0` **之前**被检查 → 报 Victory。**规模场景下所有黑舰同速同距 → 剩余多艘会在几乎同一时刻（t≈21000s）一起到线，只要全部在同 1 个裁判周期内被击杀就判 Victory** —— 这是 30v30 "胜利"的主因（见 §15/§16）。
- 白 UAV 计入 `total_white_alive`（UAV 全灭+USV 全灭 = Defeat）；UAV 死亡只影响该计数，不提供黑方击杀。
- API 映射（`main.py:1220-1247`）：「敌方所有…」→ Victory；「我方所有…」或「突破」→ Defeat；引擎停止 → 按 env_score_flat 正负。

### 6.2 时间几何（可复算，全部来自物理/脚本常量）

- 黑 USV 从 x=260000 以 10 m/s 正西 → 首舰到线（x=50000）在 t≈21000s（不被打断时）。
- 白 UAV 从 x=0 起飞 100 m/s 东飞 vs 黑 UAV 30 m/s 西飞，相对 130 m/s，60km 探测 → 首次探测 ≈ (260-60)k/130 ≈ 1538s（实测 1543-1580s，各规模一致）。
- 白 USV 20 m/s 东进 + 黑 10 m/s 西进，40km 锁距 → 首锁 ≈ (260-40)k/30 ≈ 7333s（实测 7352-7480s，各规模一致）。

---

## 7. Current Black Script

### 7.1 正式使用脚本

- **原始**：`sim_20250819测试用例1.py`（30v30，15+15）——`black_strategy` 定义在 L167-176。
- **规模场景**：`scenario_builder.build_scenario(...)` 内 `black_strategy`（L209-218）与原始完全一致（同一策略，仅数量参数化）。
- **黑方运动**（完全确定性）：
  - 15 黑 USV：`[260000, y_i]`，`cmd_sail_area(speed=10, waypoints=[260000,y]→[130000,y]→[0,y])` → **直线正西 10 m/s，永不转向、不规避**（y 固定）。
  - 15 黑 UAV：`[260000, y_i]`，t=0 已在空中，`cmd_sail_area(speed=30, 西向)`，电池 t=0 起消耗（约 t=25000s 自毁），纯侦察不改航向。
- **黑方锁定**（每秒 manipulator）：
  ```python
  detected = engine.get_black_targets()     # 所有 BLUE 单位 intel 并集（共享感知）
  for b in black_usvs:
      for w in detected:
          if "usv" in w: engine.black_cmd_lock(b.name, w)
  ```
  → 每艘黑 USV 对**检测到的白 USV**逐个尝试锁；受"一船一锁"约束，实际**每艘黑船 1v1 分散火力**：无集中、无优先级、无规避、无 UAV 指挥。黑 UAV 不锁定。
- **黑方侦察**：黑 UAV 60km±30° 给黑 USV 延长锁距到 40km（与白方对称）。
- **黑方特权**：黑方在引擎内部（`black_cmd_lock`、`get_black_targets`）直接调用引擎 API，天然知道白方真实位置（`get_black_targets` = 全局 intel）。**黑方是"全知感知 + 简单反应式锁定"**，并非"拥有白方未知特权"——只是感知模型相同、执行最简单。

### 7.2 关键区分（"开发人员知道黑脚本" vs "白 Agent 运行时知道黑脚本"）

- **开发人员**：已知黑脚本完全确定（直线西进、1v1 分散锁定）。这是设计 Agent 的背景知识，**合法**。
- **白 Agent 运行时**：**只能通过 HTTP 观测**推断敌方运动。黑方速度/位置/数量全部在线推断，代码内无任何黑方常量（公平性审计见 §13）。
- 白 Agent **不知道**"黑方永远 10 m/s 正西"——它只观测到"当前可见目标的速度是 (-10,0)"。黑方若改变脚本（下一阶段 random waypoint），Agent 仍只从观测学习。

---

## 8. White Agent V1 Architecture

### 8.1 数据流

```
AgentMain.run → client.start() (POST /start "测试用例1")
  while step<40000 and not ended:
    step_once():
      GET /status      → Obs（结构化：统计/单位/观察信息/奖励/局内时间）
      GET /legal_actions → LegalSet（动作掩码查询）
      TrackManager.update(obs)          → DETECT 事件
      TrackManager.reconcile_assigned(obs, usv_targets)  # 用引擎锁定真相同步 assigned
      TrackManager.kill_detect(obs, prev_black_killed)   # 奖励增量 + 尸体检测 → KILL
      ThreatAllocator.allocate_usvs(tracks, usvs, usv_targets, now)
      USVController.step(...)           → usv_acts
      UAVManager.step(...)              → uav_acts
      ActionSafety.filter(usv_acts+uav_acts, obs, legal)  → safe
      POST /apply(safe)
      sleep(0.05)
  GET /result → 打印 → GET /stop
```

### 8.2 各模块（逐模块）

**TrackManager**（L291）：
- 数据结构：`{name: EnemyTrack}`；`EnemyTrack`：last_position/last_velocity/last_seen_time/confidence/has_position/bearing/engaged/assigned_usvs/seen_count/last_moved_time。
- 创建：雷达捕获（active）或被动告警（passive，仅方位）。`killed_names` 防止死灰复燃。
- 更新：有观测用观测速度；`update_obs` 若位置移动>5m 更新 `last_moved_time`（尸体检测用）。
- 外推：`predicted_position = last_position + last_velocity * (now - last_seen_time)`（**常量速度点估计**）。
- 置信度：可见(30s内)=1.0；30–120s=0.5；>180s 丢弃。
- 尸体检测：`stationary_duration >= 600s` → KILL（冻结最长 300s 解冻必移动，故>600s 静止=尸体）。
- 丢失处理：`lost_high_threat`（有位置、30-120s、conf≥0.5）供 UAV reacquire。

**ThreatAllocator**（L445）：
- 威胁分 `= 1.4*prox + 0.8*vel + 1.0*conf + 0.8*alloc (+0.2 engaged)`；`prox` 由距突破线距离、`vel` 由观测 vx（负=向西）、`alloc` 由"还缺几个攻击者到 2"。
- `_is_ship(name) = "usv" in name` → 只分配敌 USV（敌 UAV 不分配火力）。
- 分配：按威胁分降序贪心；每目标常规 2v1；`x < EMERGENCY_3V1_X(150km)` 且已有 2 攻击者 → 3v1；USV 就近分配。

**USVController**（L535）状态机：`DEAD / FROZEN / LOCKING / INTERCEPTING / AVAILABLE`
- `LOCKING`：硬保持目标，持续向目标机动保持 <40km（锁断重建重计时）。
- `FROZEN`：不动不锁。
- 分配保持：`INTERCEPTING` 目标未失效绝不切换。
- **机会锁定**（P0 关键修复）：非 LOCKING/FROZEN 的 USV 若 40km 内有可锁敌舰，立即锁"攻击者最少、距离最近"的 → 避免越过可锁敌舰去追远处分配目标。
- 目标失效（被丢弃/击沉/消失）→ RELEASE。

**UAVManager**（L685）状态机：`ON_SHIP / SEARCH / REACQUIRE / RETURN / LANDING / CHARGING`
- 电量安全（核心，Commander 不可覆盖）：`est_ret = 到最近空机库存活USV距离 / 100`；`batt < est_ret + 300` → 立即 RETURN。
- 回收舰：最近且空机库的存活 USV（可跨母船）。
- 再起飞：电量 >80% 且（有 lost 高威胁 或 敌不可见）。
- REACQUIRE：`lost_high_threat` 航迹 → 飞向 `predicted_position`；每航迹最多 1 架。
- 搜索：东西条带巡逻 `SEARCH_X_MIN=140000..SEARCH_X_MAX=260000`，扇面 `(idx-8)*7°`（**V1 硬编码 15 架假设**）。
- RETURN/LANDING：距回收舰 ≤2km 且合法 → land_uav（API 自动制导）。

**ActionSafety**（L853）：死/冻过滤、`/legal_actions` 二次校验（can_move/can_lock/can_launch/can_fly/can_land）、已锁不重复、机库冲突、fly 与 land 互斥、同单位同一步只保留第一个动作。

### 8.3 V1 总结

```
Observation(/status+legal) → Belief/Track(TrackManager) → Threat Allocation(2v1/3v1贪心)
→ USV Control(FSM+机会锁定) + UAV Control(FSM+电量安全) → ActionSafety → /apply
```
V1 是**完全确定、观测纯正、无 LLM** 的基线。

---

## 9. White Agent V2 Architecture

V2 = V1 确定性执行核 + **低频率异步 LLM Commander** 战略层。**LLM 不替换执行核**。

### 9.1 数据流（相对 V1 的增量）

```
step_once():
  status/legal → TrackManager → kill_detect
  intent = commander.get_intent()          # 原子读取当前生效意图（默认 DEFAULT_INTENT）
  alloc = allocator.allocate_usvs(..., intent=intent)
  usv_acts = usv_ctrl.step(...)            # 与 V1 相同
  uav_acts = uav_mgr.step(..., intent=intent, threat_fn=...)   # 参数化
  _record_stats / trigger = _detect_trigger(obs)
  summary_text, valid_tracks = summarizer.build(...)           # 每步构建摘要
  commander.maybe_request(now, summary, valid_tracks, trigger) # 非阻塞 spawn 后台线程
  safe = safety.filter(...) → POST /apply
```

### 9.2 V2 vs V1 的真正 diff（逐模块核对）

| 模块 | V1 | V2 |
|---|---|---|
| TrackManager | 相同 | **完全相同**（逐行一致） |
| ThreatAllocator | 固定 focus=2/emg=3、无 reserve/bias/priority | **intent 参数化**：focus/emergency_focus/reserve(reserve_usvs|reserve_ratio)/threat_bias(权重)/priority_tracks(+0.3)/engagement_aggressiveness(3v1 触发距离 emg_x=150km×(0.5+agg)) |
| USVController | 相同 | **完全相同** |
| UAVManager | 固定 15 架扇面 `(idx-8)*7°`、固定 need_search | **数量自适应扇面**（`step_deg=90/n`，以 `obs.uav_alive` 为 n）+ intent(uav_mode/uav_priority/recon_aggressiveness)；电量/RTB/降落不变量保留 |
| ActionSafety | 相同 | **完全相同** |
| ApiClient | script 固定"测试用例1" | `SCENARIO_SCRIPT` 环境变量选脚本 |
| AgentMain | – | + SkillLoader/TacticalSummarizer/LLMCommander/CommanderIntentAdapter + trigger 检测 + 统计 + `[META]` 输出 |
| 自测 | selftest | + mocktest(Commander) + scaletest(规模) |

### 9.3 LLMCommander（异步非阻塞）

- API：DeepSeek/Anthropic 兼容端点 `ANTHROPIC_BASE_URL/v1/messages`，`ANTHROPIC_AUTH_TOKEN`，模型 `deepseek-v4-flash`（env `ANTHROPIC_MODEL`）；`thinking: disabled`。
- 触发：`maybe_request(now_sim, summary, valid_tracks, trigger)` 立即返回；满足 `now - last_request_sim >= 600` 且无 in-flight → 快照摘要交给后台 `threading.Thread`；主线程**永不等 LLM**。
- 失败行为：API 失败/解析失败 → 记 stats、保留 `last_valid_intent`；`LLM_ENABLED=false` → 不发起请求、始终 DEFAULT_INTENT（=V1 行为）。
- 统计：calls/parse_failures/api_failures/latency_sum；实测平均延迟 ~1.7-2.1s 实况（≈85-105 仿真秒等价）。
- trigger 检测（`_detect_trigger` 优先级）：`breakthrough_risk`(任一航迹 x<90km) > `multi_frozen`(≥3 冻结) > `friendly_loss`(USV 数下降) > `lost_high_threat` > `threat_spike`(可见敌 +3) > `first_detect` > `periodic`。

### 9.4 StrategicIntent 完整 schema

```python
posture:              cautious | balanced | aggressive          (默认 balanced)
focus_level:          1~3       常规交战每目标攻击者数            (默认 2)
emergency_focus_level:2~4       临近突破高威胁攻击者数            (默认 3)
reserve_usvs:         int 0~8  | None   旧字段：显式绝对预备数（None=用比例）
reserve_ratio:        0.0~0.5   预备比例 = 预备USV/当前可用USV     (默认 0.20) ← 已从 reserve_usvs 迁移
threat_bias:          breakthrough_eta | nearest | highest_confidence | balanced   (默认 breakthrough_eta)
priority_tracks:      list[track_id]   (必须存在于当前摘要 valid_tracks)
uav_mode:             broad_search | search_and_reacquire | focused_reacquire
uav_priority_tracks:  list[track_id]
recon_aggressiveness: 0~1       (默认 0.6)
engagement_aggressiveness:0~1   (默认 0.7)
reason:               str≤200 仅日志
```
- 迁移状态：**已从 `reserve_usvs` 迁移到 `reserve_ratio`**；`reserve_usvs` 保留为向后兼容的显式覆盖字段。
- `DEFAULT_INTENT = StrategicIntent()`（全默认）。`__eq__` 按字段全等（用于日志去重）。

### 9.5 CommanderIntentAdapter

- `extract_json_object`：括号平衡扫描器从 LLM 文本提取最外层 JSON（容忍 markdown 围栏/前后缀）。
- `validate`：POSTURES/BIASES/UAV_MODES 白名单；数值 clamp（focus 1-3、emg 2-4、reserve_usvs 0-8、reserve_ratio 0-0.5、recon/engage 0-1）；`priority_tracks/uav_priority_tracks` 对照 valid_tracks 过滤无效 id。
- 任何失败返回 `(None, reason)` → 调用方 `_worker` 保留 `last_valid_intent`（`latest_intent` 字段原子更新）。

### 9.6 deterministic fallback

- `LLM_ENABLED=false` → `maybe_request` 直接 False，`get_intent()` 恒为 `DEFAULT_INTENT` → 全链路 = V1 确定性核心（UAVManager/Allocator 用默认参数）。单测覆盖。

---

## 10. Maritime Skill

`skills/maritime_commander/SKILL.md`（142 行）分类：

- **Platform Mechanics**：USV 35km 全向、锁 <40km、一船一锁、2 命中击沉、300s 窗口 80%、首命冻结 300s、UAV 60km±30° 前向扇区、共享感知、2v1/3v1 来自锁链机制。
- **Fair-play Doctrine**：Commander 只用 friendly state / radar observation / TrackManager 航迹 / 已公开平台规则 / engagement state；禁止敌方 true position/velocity、internal state、script 名称、initial layout、固定数量/轨迹/速度。
- **USV Doctrine**：focus fire > 1v1；只投入达成局部数量优势所需力量（2v1 默认、紧急 3v1）；已锁不切换；2v1/3v1 与规模无关（机制本身）。
- **UAV Doctrine**：侦察/感知资产非战斗；优先搜索未知区域/未交战威胁/reacquire 高威胁 lost track；扇区随可用数量自适应；电量/RTB 由确定性 UAVManager 管理。
- **Information Doctrine**：不识别 script 名称，按 position/velocity/confidence/threat/集中度/航向变化判断态势；敌方行为变化 → 通过新观测调整 intent，不切换"针对脚本 A/B/C"的固定模板。
- **Resource Doctrine**：预备力量是**比例**（reserve_ratio 0~0.5）而非固定数量；敌情不明高、临近突破降到 0；规模不同同一策略自适应。
- **Commander Role**：只输出战略级 intent，禁止坐标级 move/动作字符串/单艇航路/UAV 电量/重复 lock timing。

### 10.0 报告与代码冲突记录（以代码为准）

| # | 冲突点 | 报告说法 | 代码/数据实际 |
|---|---|---|---|
| 1 | UAV 败局损失原因 | scale 报告 §8"基地被突破端冲毁" | 实际是 UAV RTB 无回收舰后**西飞出 x<0 被裁判击杀**（game1 逐事件证实，见 §16.3） |
| 2 | 30v30 胜局性质 | scale 报告将 3 胜视为 agent 能力 | 3 场胜全部靠**引擎结束顺序 quirk**（突破计数 2/3/3，victory_time≈21147s），干净竞速胜为 0/10（见 §15.3） |
| 3 | Commander 超时 | V2 报告 §7.1 "默认 12s" | 代码 `COMMANDER_TIMEOUT_S = 60`（agent_hybrid_v2.py:94） |
| 4 | 引擎实际速率 | V2 报告 "约 13-40×" | CSV wall/sim 反推约 48-51×（含 stop 睡 2s 等开销，引擎实际更高） |
| 5 | V1 冒烟胜率 | V1 报告 11 局 8 胜 ≈73% | 该批 /tmp 日志已不存在，无法复核；当前可复现数据只有 40 局 scale 评估 |

### 10.1 长期稳定知识 vs 潜在过拟合

**稳定知识（长期有效）**：focus fire、信息先于投入（information before commitment）、UAV 作为感知资产、预测不等于真值、比例化 reserve、扇区随数量自适应。

**潜在过拟合 / 需警惕点**：
- Skill 中没有写死 "10v10/30v30/5 USV/15 USV" 等数量（audit 13/13 PASS 确认无规模标签）。
- 但 Skill 的无人机"搜索未知区域/重搜"思想与当前确定性搜索条带（140–260km）隐含"敌从正东来"的几何假设——**若下一阶段敌随机机动/从其它方向来，Skill 没有直接错误，但 Agent 的确定性搜索策略没有对应能力**。
- "UAV 电量与 RTB 由确定性 UAVManager 管理"——当前 UAVManager 的 RTB 在"无回收舰"时会失效（见 §16），Skill 层面未体现这一边界。

---

## 11. Tactical Summary & StrategicIntent

### 11.1 TacticalSummarizer（`agent_hybrid_v2.py:736-823`）

- 输入：`Obs`（/status 白名单）+ TrackManager 航迹 + USV/UAV 状态机 + 当前 intent。**不读取 raw legal_actions 全文**（LegalSet 只提取动作集合用于合法性）。
- 输出：`(text, [track_names])`；格式固定：
  ```
  TIME / MISSION(prevent breakthrough) / FRIENDLY(usv_alive/available/engaged/frozen, uav_airborne/searching/returning/charging)
  KNOWN ENEMY TRACKS: count= / visible= / lost= / engaged= / unassigned=
      <track>: visible / position / velocity / confidence / threat / attackers / engaged   (top-K 详细)
  TOP THREATS: 1..K
  ENGAGEMENT: targets_engaged / targets_unassigned
  RECON: lost_high_threat_tracks / uav_coverage_summary
  CURRENT COMMANDER INTENT: <intent.describe()>
  ```
- **规模无关**：`K = min(8, len(tracks))`，超出 K 用聚合计数（"N more tracks not detailed"）；无场景标签（audit 确认 MISSION 只写 "prevent breakthrough"）。
- 摘要大小：实测 ~1.7k 字符 ≈ 500-600 token（top-K 封顶），与规模无关。

### 11.2 StrategicIntent 与确定性策略联动

| intent 字段 | 联动点 |
|---|---|
| focus_level / emergency_focus_level | ThreatAllocator 的每目标攻击者上限（want=focus-cur） |
| reserve_ratio / reserve_usvs | `reserve=round(len(available)*ratio)`，非紧急才留；紧急(有目标 x<emg_x) 归零 |
| threat_bias | 威胁分权重（breakthrough_eta: prox 1.9×；highest_confidence: conf 1.8×；nearest: 近距加成） |
| priority_tracks | 威胁分 +0.3 轻量加分 |
| engagement_aggressiveness | `emg_x = 150km × (0.5+agg)`（越积极越早 3v1） |
| uav_mode / uav_priority_tracks | lost 排序（focused_reacquire 优先指定 track） |
| recon_aggressiveness | 再起飞搜索投入（recon≥0.8 才额外起飞） |

---

## 12. Deterministic vs LLM Responsibilities

| 职责 | 执行者 | 依据 |
|---|---|---|
| 单艘 USV move/lock 指令、目标切换禁止、距离保持 | **确定性 USVController**（硬编码） | USVController.step |
| UAV 电量安全、RTB、降落制导、再起飞阈值 | **确定性 UAVManager**（不变量，Commander 不可覆盖） | UAVManager.step L1284-1287 |
| 2v1/3v1 目标分配、reserve 计算 | **确定性 ThreatAllocator**（参数由 intent 提供） | allocate_usvs |
| 动作合法性过滤 | **确定性 ActionSafety**（全动作过 /legal_actions） | ActionSafety.filter |
| 敌情航迹建/外推/置信/丢弃/尸体 | **确定性 TrackManager** | TrackManager |
| 战略姿态（posture）、火力集中度（focus）、预备比例、威胁偏向、UAV 搜索重点、激进度 | **LLM Commander**（每 ≥600 仿真秒，异步） | StrategicIntent |
| 3v1 触发距离、recon 力度微调 | intent → 参数化联动 | 见 §11.2 |

**为什么 LLM 不直接输出 move/lock/fly**：
1. **延迟不可行**：引擎 50× 实时永不等待；每步 LLM 调用 1.7-2.1s 实况 = 85-105 仿真秒漂移，锁距 40km 内会把攻击 USV 推出锁距 → 锁断重计时。早期 `agent_llm.py` 每步调 LLM，30v30 不可行（recon 报告 §10 论证）。
2. **token 不可行**：30v30 全量 obs+legal ≈ 15-30k token/步；纯 LLM 决策 token 爆炸。
3. **可验证性/安全性**：具体动作必须过 /legal_actions 与实时状态双重校验；LLM 直接输出动作串会产生大量非法动作（V1 的 400 批量失败教训）。
4. **架构原则**：确定性控制器保证"每个宏观步都正确"，LLM 只调整"资源配置与交战姿态"（报告 §8 设计）。

**async Commander 为什么重要**：
- 主循环每步（~20-30 仿真秒）不能等待 LLM；后台线程 + 锁 + 快照摘要保证 `maybe_request` 立即返回（单测实测 <0.2s）。
- `in_flight` 保护保证同时间仅 1 个请求；600s cooldown 使请求量受控（实测 15-35 次/局）。
- 失败时保留 `last_valid_intent`，绝不降级为"无指挥"。

**fallback 链路**：`LLM_ENABLED=false` → 无请求 + DEFAULT_INTENT → 全确定性；LLM API/parse 失败 → 保留上一有效 intent；`SkillLoader` 失败 → 内嵌最小 fallback doctrine。

---

## 13. Fair-Play Boundary

### 13.1 审计方法

对 `agent_hybrid_v1.py / agent_hybrid_v2.py / skills/` 逐项 grep 并人工判断。

### 13.2 审计结果（逐项判断）

| 检查项 | 结果 | 说明 |
|---|---|---|
| `black_usv / black_uav / black_strategy / BLACK_Y` | 命中仅为**注释**与**自测禁止清单** | v1 只在文件头注释；v2 仅在 `mocktest_commander` 的 `forbidden` 断言（证明摘要不含）与 `scaletest` 测试夹具（`black_usv{i}` 造航迹） |
| `ENEMY_X / 260000 / vx=-10 / velocity -10` | **无运行时命中** | 唯一 `(-10,0)` 出现在 selftest 夹具（模拟一次观测到的速度） |
| `simulation.core / tzb_engine / import simulation / grpc` | **0 命中** | Agent 完全不导入引擎、不直连 gRPC |
| `engine.black_* / get_state().black_*` | **0 命中** | 无引擎调用 |
| 已知敌方总数量 | **否** | `enemy_visible` 是"可见敌数"（观测），非总量；唯一黑方计数是奖励信号 `black_killed`（累计击杀，允许的公共信号）；总量只能由观测推理 |
| 已知敌人真实位置 | **仅观测时** | 位置来自雷达捕获（真值），30s 黏性后消失；尸体残留在 intel |
| 已知敌方固定速度 | **否** | 速度只用观测字段；`threat_score` 的 `vel` 用观测 vx，绝无硬编码 |
| 已知当前 black script 名称 | **否** | Agent 不读 sces.json、不读脚本名 |
| 直接访问 simulator engine | **否** | HTTP-only |
| 绕过 POMDP API | **否** | 全部动作过 `/apply`；观测过 `/status` |
| TacticalSummarizer 泄露 truth state | **否** | 只打包 Obs 白名单 + TrackManager 航迹（自测断言不含 black runtime truth） |

### 13.3 结论

> **White Agent（V1 与 V2）是 observation-pure 的。** 运行时唯一输入 = HTTP 观测（/status white_observation + 白名单 + 奖励信号）与 /legal_actions。对黑方的全部运动学（数量、位置、速度、航向）从观测在线推断，无任何先验注入。

### 13.4 边界注意（合法但需知晓）

- `_is_ship(name) = "usv" in name`：依赖**黑方单位命名约定**（观测到的名字含 "usv"）。这是策略对命名的耦合（观测名称来自 API），不属违规，但若未来黑方命名变化，火力分配会失效。
- L4 身份泄漏：被动告警带攻击者**名字**（`_build_enemy_intel`），可反查敌编队存在性/编号。API 设计如此，非 Agent 违规。
- L5 幽灵被锁：`locked_attacker`（`emy_name`）只增不删，被动告警可能长期报"被锁"，Agent 应以 `is_locked` 布尔为准（当前 Agent 的 USVController 不依赖 `is_locked` 决策，影响低）。

---

## 14. Scale Generalization Implementation

### 14.1 场景参数化

- `scenario_builder.build_scenario(white_usv, white_uav, black_usv, black_uav, ...)`。
- 4 个 wrapper 只传数量：10v10=(5,5,5,5)、15v15=(8,7,8,7)、20v20=(10,10,10,10)、30v30=(15,15,15,15)。
- 部署公式：`_deploy_ys(count) = linspace(405000 − span/2, 405000 + span/2, count)`，**恒定 15km 舰间距**。
- y 对齐：**黑方 USV/UAV 的 y 直接取 `white_ys[_i-1]`**（即黑方使用与白方相同的 y 列表，但取前 black_count 个）。
- 黑方运动/策略与原始 30v30 完全一致（隔离规模变量）；`set_ratio(50)` 统一。
- 注册：`sces.json` 4 条目 + `pomdp_api AVAILABLE_SCRIPTS` 4 条目。

### 14.2 Agent 侧规模无关化改动（V2）

- `SCENARIO_SCRIPT` 环境变量选脚本（query param）。
- `reserve_ratio`（0~0.5，默认 0.20）替代绝对 reserve。
- `available < reserve + desired` 动态降级。
- UAV 扇面按 `n_uavs = max(1, obs.uav_alive)` 自适应（去掉 V1 的 `(idx-8)*7` 15 架假设）。
- TacticalSummarizer top-K=8 + 聚合。

### 14.3 实验控制（run_scale_eval.py）

- 同一 agent（`agent_hybrid_v2.py`，`--uavs` 为 no-op，默认启用 UAV）+ 同一 Skill + 同一 prompt；仅 `SCENARIO_SCRIPT` 不同。
- 每规模 10 局、共 40 局；RNG 自然变化，**失败局不重跑**。
- 可断点续跑（CSV 已存在 (scale,game) 跳过）。
- Skill hash 冻结 `e1f7839a...`（与当前文件一致）。
- 每局指标从日志 `[META]` 与每步采样解析。

### 14.4 已发现的 confound（重点标注）

1. **固定 15km 间距 → frontage 随规模变化**：10v10 frontage=4×15=60km；30v30=14×15=210km。**规模改变 → 正面宽度同时改变**，且正面密度随规模不同。这是实验 confound（报告自己也承认）。
2. **y 对齐不对称（15v15 等非对称编成）**：15v15 白 8 USV 但黑仅 7 UAV 用 `white_ys[0:7]`（缺第 8 个 y 位置），黑 UAV 覆盖少一个 y 线；白 USV8 在最北 y 无黑 UAV 对应。规模/编成变化时黑方 UAV 覆盖与白方不对称。
3. 黑 UAV 数 < 黑 USV 数（15v15、以及所有规模黑 UAV 与黑 USV 的 y 从同一列表前 N 个取）→ 黑方 UAV 只在部分 y 线提供 60km 前向预警。
4. 非对称编成的"规模标签"：`scenario_15v15` 实际是 8USV+7UAV vs 8USV+7UAV（同名"15v15"但每方动态单位总数=15）。`10v10` 才是对称 5+5。**"v" 后的数字是总单位数，不是 USV 数**。

---

## 15. Scale Generalization Results

### 15.1 我的独立统计（与聚合表一致）

| Scale | n | Wins | WinRate | Avg Kill | Avg USV Loss | Avg UAV Loss | Avg Victory Time(s) | Avg LLM Calls | Avg Wall(s) |
|---|---|---|---|---|---|---|---|---|---|
| 10v10 | 10 | 3 | 30% | 3.7 | 4.8 | 3.5 | 8754 | 17.4 | 208 |
| 15v15 | 10 | 6 | 60% | 7.5 | 7.1 | 2.8 | 13361 | 21.3 | 260 |
| 20v20 | 10 | 4 | 40% | 8.6 | 9.5 | 6.6 | 16127 | 24.6 | 299 |
| 30v30 | 10 | 3 | 30% | 13.6 | 14.2 | 9.0 | 21145 | 30.9 | 397 |
| TOTAL | 40 | 16 | 40% | | | | | | |

验证：CSV 恰好 41 行（1 表头 + 40 数据）；每规模 10 局；无失败重跑（notes 全空）；LLM parse failures 全 0.0；avg focus ≈ 2.0（各规模恒定）；avg reserve_ratio 0.08–0.26。

### 15.2 胜局形态（逐局核实）

- **所有胜局 = 全歼黑 USV**（kills == black_usv 数），15/16 胜局 UAV 损失 0（唯一例外 20v20 g9 损失 6，见 §15.3 quirk 分析）。
- **但胜局我方 USV 损失极高**：10v10 胜局 4-5/5、15v15 6-7/8、20v20 7-10/10、30v30 12-14/15。**即使是胜局也接近相互歼灭**。

### 15.3 我发现的 quirk 胜利（本侦察的核心新发现）

按每局日志的 `突破:` 计数重新分类：

| Scale | 胜局明细 | 突破计数 | 判定 |
|---|---|---|---|
| 10v10 | g6 (8626s) / g8 (8982s) / g9 (8655s) | 0 / 0 / 0 | **干净击杀竞速胜**（早于 21000s 截止，无突破） |
| 15v15 | g1/g4/g5/g6/g9/g10 | 全部 0 | **干净击杀竞速胜** |
| 20v20 | g2/g6/g7 | 0 | 干净胜 |
| 20v20 | g9 (21002s) | **1** | **quirk 胜**（1 艘黑舰突防被裁判击杀，最后一艘时 black_ship_alive→0 先判 Victory） |
| 30v30 | g4 (21147s) | **2** | **quirk 胜** |
| 30v30 | g6 (21147s) | **3** | **quirk 胜** |
| 30v30 | g9 (21142s) | **3** | **quirk 胜** |

**结论（verifiable）**：
- **30v30 的 3 场"胜利"全部是 quirk 胜**——agent 在击杀竞速中失败（12-13 杀后 2-3 艘黑舰存活），剩余黑舰同时（t≈21000s）突防，全部被裁判击杀后才因 `black_ship_alive==0` 判 Victory。真实击杀竞速胜率 30v30 = **0/10**。
- **20v20 的 4 胜中 1 胜是 quirk**（g9）→ 真实竞速胜 3/10。
- **15v15 的 6 胜全部干净**（击杀在 9679-16940s 完成，全部无突破）。
- 若不修正 quirk，"胜率倒 U 形（30→60→40→30）"应修正为**干净竞速胜率 10v10=30%、15v15=60%、20v20=30%、30v30=0%** —— 单调递减，30v30 彻底无法完成击杀竞速。

**因此报告结论需要修订**：
1. "Q1 无规模退化" 不成立 —— **30v30 击杀竞速能力是 0（10 局全未能杀光黑舰）**，报告把 quirk 当成了 agent 能力。
2. "Q2 退化来自哪里" —— 30v30 的失败不是"正面太宽的协调负担"能解释的，而是**火力枯竭**：白方 USV 在对称对杀中先被拼光，剩余黑舰无法再被锁定（无 USV 锁距内）。
3. "15v15 温和最优" 仍然成立（60%，且全部干净）。

### 15.4 实验"验证了什么 / 没验证什么"

**已验证**：
- 同一 agent/skill/prompt 在 4 种规模下都能跑通，无崩溃、无非法动作灾难。
- LLM Commander 跨规模行为一致（focus≈2、解析 0 失败、延迟平）、摘要规模无关（top-K）、调用次线性（3× 单位 → 1.8× 调用）。
- 感知/航迹满编（max_known_tracks = 10/15/20/30），无规模性感知丢失。
- 首侦/首锁时间跨 40 局不变（几何不变量），说明无先验注入（但见 §15.5 反向说明）。

**没验证**：
- **没有验证"agent 在更大规模下能赢"** —— 30v30 击杀竞速实际为 0/10。
- **10 局/规模在 ±30% 置信区间内不足以统计区分** 30/40/60%（报告自己承认），更不足以宣称 15v15 显著优于其它。
- **没有验证"skill/policy 泛化到其它黑方脚本"**（黑方本轮不变）。
- **没有验证"随机路径/机动目标"**。

### 15.5 关于"首锁时间恒定 = 无先验"的证伪提示 [推断]

报告以"首锁 ~7380s 跨 40 局一致 → 证明无 vx=-10 注入"。实际上，**因为黑方本来就是直线 10 m/s 正西，一个假设 vx=-10 的作弊 agent 会得到完全相同的首锁时间**。首锁恒定只能证明环境确定性，不能区分"干净 agent 从观测学到的速度"与"作弊 agent 的硬编码先验"。真正的公平性证据是代码审计（§13）。

---

## 16. 10v10 Failure Analysis

### 16.1 规模定义确认

- `scenario_10v10.py`：`build_scenario(white_usv=5, white_uav=5, black_usv=5, black_uav=5)` → **每方 5 USV + 5 UAV**（对称 10 单位/方）。确认无误。
- 首侦 ~1546-1554s、首锁 ~7352-7412s（与几何一致）。

### 16.2 10v10 失败模式（逐局日志诊断，game1 vs game6 对比）

**共同剧情**（10 局全部一样）：
1. t≈0-100s：5 UAV 起飞（搜索条带 140-260km），5 USV 全速东进 20 m/s。
2. t≈1545s：黑 UAV 被探测（x≈210km）。
3. t≈1800-1900s：黑 USV 被探测（x≈190km），5 USV 全部进入 INTERCEPTING（2v1 贪心分配：初始只覆盖其中 2-3 个目标，其余 1-2 艘黑舰在探测到后再补分配；game1 中 black_usv3/4 各 2 艘、black_usv2 1 艘）。
4. t≈1850-7350s：**长距离追击**（USV 从 x≈0 向东跑到 x≈147km 才进入 40km 锁距，耗时 ~5500 仿真秒；黑舰同期从 x≈190km 西进到 x≈186km。途中 USV 全程 int=5，无交战）。
5. t≈7355s：首锁。随后 ~800s 内爆发对杀。
6. t≈8100-8400s：白 USV 5→0 迅速阵亡（互锁竞速 80% 骰子）。
7. 胜负分界：
   - **胜局（g6/g8/g9）**：5 艘黑舰全部被击沉（最后一杀靠既有锁链在攻击者死亡后继续结算），且白 UAV 全部存活 → `black_ship_alive==0` 判 Victory（8626-8982s）。
   - **败局（g1-5/g7/g10）**：仅杀 1-4 艘黑舰，1-2 艘黑舰存活继续西进；白 UAV 全灭 → `total_white_alive==0` 判 Defeat（10701-11221s）。

### 16.3 败局 UAV 全灭的真实机制（重要，报告有误）

报告 §8 写"败局 UAV 全灭（基地被突破端冲毁）"。**实际（game1 逐事件核实）**：
- t≈8280s：白 USV 只剩 2 艘，全部 UAV 触发 RTB，原因日志：`电量16672<inf+300` —— 即 `recovery=None`（**没有"空机库"的存活 USV 可选**，因为最后 1-2 艘 USV 机库被占用/已死）→ `est_ret=inf` → `batt < inf+300` 恒真 → **全部 UAV 被强制进 RETURN**。
- RETURN 且 `recovery is None` → 代码 `continue`（不发任何新指令）→ UAV 保留最后一条持久飞行指令。
- 5 架 UAV 沿最后航向**继续西飞**（x 从 ~170km 单调降到 ~0）。
- t≈10134-10906s：UAV 依次飞越 x<0（任务区域 x∈[0,300000]），被裁判 `judge_system` "不在设定区域内 → kill"。
- 5 架 UAV 全灭 → `total_white_alive=0` → **"我方所有单位被击毁" → Defeat**（black_breakthrough=0）。

**这是确定性 bug，不是 RNG**：`UAVManager` 的 RTB 逻辑把"无空机库可用"误判为"必须返航"，且无回收目标时不发指令、保留旧航向导致西飞出界。此 bug 在所有败局（UAV loss=5/7/10/15）都发生，直接影响 `total_white_alive` 进而决定胜负判定。

### 16.4 10v10 诊断结论

- **对称 5v5 对杀竞速是纯 RNG 方差**（2 发命中、80% 骰子、300s 窗口）→ 胜率 30% 主要由骰子决定。
- **攻击者分配不足**：5 艘 USV 对 5 艘黑舰 = 1v1 偏多（focus=2 需要 10 艘才够 2v1）；黑方 1v1 分散，白方 1v1 竞速近似五五开 → 先手冻结与命中时序决定胜负。
- **UAV 在关键时刻缺席**：对杀窗口（7355-8400s）内 UAV 电量 ~16600（>80% 阈值 20000 之下），无法再起飞；且 USV 全灭后 UAV 全部西飞出界。UAV 对击杀竞速零贡献。
- **长追击空窗**：t≈1900-7350s 的 ~5500s 中 USV 只跑路不交战，期间黑舰以 10 m/s 西进 ~55km。
- **first detection / first lock 均非 agent 能力**（几何不变量）。

---

## 17. Random-Waypoint Risk Analysis

下一阶段计划引入"不同兵力数量 + random waypoint / maneuvering enemy paths"。当前架构对随机轨迹的问题（只诊断，不修改）：

### 17.1 TrackManager（风险最高）

- 只有**常量速度点估计**（`predicted_position = pos + vel·dt`）。敌方一旦转向：
  - **预测误差随丢失时间线性~二次增长**（无不确定性椭圆/region）。
  - **confidence 不反映机动**：confidence 只由"多久没看到"决定（30s 内 1.0 / 30-120s 0.5 / >180s 丢），与"预测是否可靠"无关。
  - 丢失 >180s 直接丢弃航迹 —— 机动目标一旦被甩，直接失去记忆。
- 无 velocity smoothing/滤波：观测速度直接采用，转向瞬间的瞬时速度会被当成持续速度外推（+180s 会错很远）。
- **影响**：UAV reacquire 飞向错误的预测点；USV 拦截向错误点追；threat_score 用预测位置算 prox/vel，转向后威胁评估失真。

### 17.2 UAVManager（风险高）

- REACQUIRE = 飞向 `track.predicted_position`（点目标），不是搜索区域/概率分布。
- 搜索策略只有东西条带 140-260km（`_search_fly` 扇面 ±45° 围绕正东/正西）——**假设敌从正东来**；机动敌可能从其它方向/折返，搜索带覆盖不了。
- RTB 的 `recovery=None → est_ret=inf → 全 RTB` 缺陷（§16.3）在随机场景下更易触发（USV 散开/机库占用随机）。

### 17.3 ThreatAllocator

- 过度信任预测 ETA：threat_score 用 `predicted_position` 的 x 与 vx；转向后高估/低估威胁。
- `_is_ship` 依赖命名。
- 若黑方机动使多目标汇聚，alloc 排序仍按点估计，可能让多艘 USV 追同一个错误预测点。

### 17.4 USVController

- 持续追击预测点，无 standoff/lead 补偿；转向目标会让 USV 蛇形追尾。
- 机会锁定（40km 内攻击者最少最近）仍是"当前可锁"的合理兜底，但**目标机动时 40km 锁距窗口转瞬即逝**。
- 对"先失去再重获"的目标无鲁棒（TrackManager 丢弃后只能重新 DETECT）。

### 17.5 Commander / Summary

- 摘要含 `velocity`（单点）与 `confidence`（只反映可见性），**不含机动性/不确定性度量**（无 heading change rate、无 uncertainty 半径）。
- LLM 只能基于"一次外推点 + 置信度"判断 —— 随机路径下信息不足。
- 敌 UAV 被当作高威胁（threat_score 中 vel 项被 30 m/s 撑满）占满摘要 top-K，浪费 Commander 注意力（现脚本即已出现，见 §12 风险）。

### 17.6 结论

**random waypoint 最可能破坏的模块依次：UAVManager（reacquire 点追 + 搜索带几何）+ TrackManager（点估计外推/机动失配）→ ThreatAllocator（ETA 失真）→ USVController（追错点）。** 对架构而言是"预测-控制闭环"整体对机动鲁棒性不足。

---

## 18. Current Technical Debt / Risks

### 18.1 确定性 bug / 缺陷（代码确认）

1. **UAV RTB 无回收舰 → 全 UAV 西飞出界**（`UAVManager.step` 的 `recovery=None → est_ret=inf → RTB` + RETURN 无目标不发指令）→ 直接造成大量 Defeat（UAV loss 全灭）。这是**所有败局的标准结局机制**。
2. **尸体永久残留 intel**（引擎 quirk）→ Agent 必须依赖"静止>600s"尸体检测，存在对撞/误判空间；被锁尸体上持续浪费锁直到被杀检测。
3. **`_is_ship` 命名耦合**（"usv" in name）——黑方命名变化即失效。
4. **V1 的 UAV 扇面硬编码 15 架**（`(idx-8)*7`）——V1 在非 15 架规模下搜索扇面错误（V2 已修）。
5. **引擎结束顺序 quirk**：最后一艘突防 = Victory —— 让"胜利"统计失真（§15.3）。
6. **`--uavs` 为 no-op**（V1/V2 只解析 `--no-uav`），评估脚本语义与实现不符（无功能影响）。
7. **`/legal_actions` 在满可见时 ~500 条/2.5万+ 字符**（30v30），Agent 虽不直接喂 LLM，但每步 HTTP 传输与解析开销大。

### 18.2 工程风险

- **无自动化回归**：无 pytest 套件；自测是 `if __name__` 手写断言，未接入 CI。
- **引擎 DB 双源**：`cache_json.pkl`（运行时）与磁盘 `json` 不一致（max_speed 20 vs 10、radar_update_time 30 vs 5）；运维重建缓存会改数值（PLATFORM_CAPABILITIES 明确提示）。
- **gRPC 直连可拿到黑方真值**（`black_usv_states`/`num_black_*` 在 raw 里）——公平性依赖"Agent 只走 HTTP 且不旁路"，部署时不应开放 gRPC 到 Agent。
- **评估可复现性弱**：40 局只留 CSV/日志；`/tmp` 冒烟日志已不存在；RNG seed 不可控。
- **LLM 依赖外部 API**：无 key 时静默降级 DEFAULT_INTENT（行为无提示）；API 波动影响评估结果。
- **wall-clock 成本**：30v30 单局 ~6-7 分钟墙钟（CSV wall 397s），40 局 ~3.5 小时；参数/策略实验迭代慢。

---

## 19. High-Value Future Improvement Areas

> 仅建议方向，不修改代码。

1. **修复 UAV RTB 缺陷（P0）**：`recovery=None` 时不应全部 RTB；应让 UAV 悬停/盘旋/降速并等待，或选择"最后一个存活 USV"作为降落点；RETURN 无目标时给一个安全保持指令（如盘旋），杜绝西飞出界。此修复可直接改善所有败局。
2. **击杀竞速（P0，10v10/30v30 的核心）**：
   - 对杀窗口内 UAV 无用（电量 <80% 无法再起飞）——考虑降低再起飞阈值或按"交战窗口"临时放行。
   - 追击空窗（t≈1900-7350s）——USV 可先向东推进更远/更快建立接触，或允许"边跑边侦察"。
   - 30v30 火力枯竭 → 需要"保存 USV"策略（减少 1v1 对赌），例如优先 3v1 快速减员黑舰数量。
3. **Tactical/Summary 质量**：区分敌 USV（突破威胁）与敌 UAV（侦察，非突破）；摘要加机动性/不确定性度量（heading change、uncertainty radius）。
4. **TrackManager 机动鲁棒性（随机路径前置）**：引入轻量滤波/外推（如固定误差增长模型、机动检测、多假设点），或至少给预测位置加不确定性半径用于分配/重搜。
5. **reacquire 改为"搜索区域"而非点**：对 lost track 按"预测点 ± 不确定半径"扫描。
6. **评估管道**：接入 pytest/CI；固定 RNG seed 控制；加入 quirk 修正（将"最后一艘突防"单列统计，区分真实竞速胜率）。
7. **黑方脚本泛化实验**（报告 §17 已列）：固定规模变化黑方策略（zigzag/concentrated rush/多波次）。
8. **明确结束顺序语义**：若比赛方不希望 quirk 计入胜率，需在 API/统计层将"最后突防"单独标记（需与任务方确认规则解读，勿擅改引擎）。

---

## 20. Verified Facts vs Inferences

### 20.1 Verified Facts（源码/配置/CSV/日志直接确认）

- 运行链路 Agent→:8000→gRPC→base_server→sim_server→engine，引擎后台线程持续运行（`sim_server.init` + `engine.update`）。
- `black_*`/`num_black_*` 不在 HTTP 层透出（grep 确认）；Agent 无引擎/gRPC 导入；fair-play 审计干净。
- 平台数字：USV 20 m/s、锁 <40km、300s 窗口 80%、2 命中击沉、冻结 300s、UAV 60km±30°/150 m/s(/fly 上限 100)/25000s 电池、35km/30km 雷达、judge destination=50000、区域 x∈[0,300000]。
- 尸体 quirk：`locker.locked` 击沉后不复位（代码 return 早退）；尸体永久残留 intel。
- 结束顺序：`total_white_alive==0` → `black_ship_alive==0` → `black_breakthrough>0`（`tzb_engine.get_state`）。
- 40 局 CSV：41 行、每规模 10 局、无失败重跑、parse failures 0；胜率 30/60/40/30；胜局全歼；胜局 USV 损失 60-90%。
- 30v30 3 场"胜利"均有突破计数（2/3/3）且 victory_time≈21147s；20v20 g9 突破 1；15v15/10v10 胜局突破 0。
- 败局 UAV 全灭由"西飞出界"导致（game1 逐事件：UAV 单调西飞、x→0、死亡时间与到 x=0 时间吻合、`我方所有单位被击毁`、突破=0）。
- 首侦 ~1543-1580s、首锁 ~7352-7480s（几何不变量）。
- V2 的 StrategicIntent 已用 `reserve_ratio`（`reserve_usvs` 保留兼容）；TacticalSummarizer top-K=8；UAV 扇面数量自适应。
- Skill 文件 hash 与 `SKILL_MD_SHA256.txt` 一致；`audit_scale_generalization.py` 结构上 13 项检查（报告称 PASS）。
- `scenario_10v10` = 5USV+5UAV vs 5+5；15v15=8+7 vs 8+7；20v20=10+10；30v30=15+15。
- `--uavs` 未被解析（no-op）；`--no-uav`/`--selftest`/`--mocktest`/`--scaletest` 被解析。

### 20.2 Inferences（显式标注）

- **[推断]** 引擎实际 ratio ≈ 48-51×（从 CSV wall/sim 比例反推，含 stop 睡 2s 等开销）。
- **[推断]** 30v30 真实击杀竞速胜率 ≈ 0/10（3 场"胜"均为 quirk；无法 100% 排除"恰在同 1 裁判周期内全部到线被击杀且该判 Victory"是设计意图，但证据强烈支持 quirk 主导）。
- **[推断]** 15v15 胜率 60% 相对最优的机制 = 预备后 ~6 艘可投入、同时覆盖 3 目标、冗余度吸收早损（报告 §13 解释，方向合理但非我独立实验验证）。
- **[推断]** UAV 西飞出界的"最后航向"具体来自 `_search_fly` 的向西腿（d=-1）或历史 reacquire 指令——已确认单调西飞且到 x=0 即死，具体指令来源未逐一确证。
- **[推断]** 纯 LLM 每步决策在 30v30 下 token+延迟不可行（沿用 recon 报告论证，未亲自复测）。
- **[推断]** 报告将败局 UAV 全灭记为"基地被突破端冲毁"与事实不符（实为西飞出界）。

---

## 21. Open Questions

1. **quirk 胜利的规则解读**：比赛方/任务方是否把"最后一艘黑舰突防但引擎判 Victory"算作真胜？这直接影响 20v20/30v30 的胜率语义。需要与任务方确认，**不要擅改引擎**。
2. **引擎 DB 缓存版本**：`cache_json.pkl` 与磁盘 json 不一致的根因？正式评估前是否需要在真实启动的 sim_server 上核对（max_speed=20、radar_update_time=30）？
3. **UAV 在 USV 全灭后的正确行为**：规范是否允许 UAV"无母舰降落/闲置保持"？引擎对飞出区域只有 kill，无软边界。
4. **"敌 UAV 是否威胁"语义**：当前 threat_score 把黑 UAV 当高威胁（vel 撑满），Commander 被误导——应如何处理侦察机威胁（观测层面）？
5. **random waypoint 场景是否同时改变黑方锁定策略**（如集中火力/规避）？还是仅运动轨迹随机？
6. **RNG 控制**：40 局自然随机无法复现；是否需要 seed 化以支撑统计？
7. **V1 是否仍为必须维护的基线**：V1 的 15 架扇面假设在非 15 架规模下已错误，若 V1 需支持规模实验需修；否则 V2 是唯一正式 Agent。
8. **`audit_scale_generalization.py` 的 13/13 PASS**：已在本轮重跑确认（当前代码仍全绿）。

---

## 附录 A：V1/V2 关键行号索引（便于后续工作）

| 内容 | 位置 |
|---|---|
| V1 主循环 | `agent_hybrid_v1.py:964-1055` |
| V2 主循环 | `agent_hybrid_v2.py:1510-1558` |
| V2 Commander 层 | `agent_hybrid_v2.py:829-916`（LLMCommander）、`736-823`（TacticalSummarizer）、`630-730`（Adapter）、`438-507`（StrategicIntent） |
| V2 机会锁定 | `agent_hybrid_v2.py:1158-1178` |
| UAV RTB 缺陷点 | `agent_hybrid_v2.py:1282-1287`（`recovery=None → est_ret=inf → RTB`）+ `1309-1325`（RETURN 无目标 continue） |
| UAV 数量自适应扇面 | `agent_hybrid_v2.py:1339-1358` |
| 结束判定 | `hsystem/simulation/core/tzb_engine.py:120-135` |
| 尸体 quirk | `hsystem/simulation/arsenal/locker.py:112-119` |
| 共享感知 | `hsystem/simulation/core/engine.py:246-272` |
| 被动告警构建 | `hsystem/pomdp_api/main.py:650-698` |
| /status 白名单 | `hsystem/pomdp_api/main.py:1601-1659` |
| 突防判定 | `hsystem/simulation/arsenal/judge_system.py:86-113` |
| 场景参数化 | `hsystem/sim_script/20250819TZB/scenario_builder.py` |
| 黑方策略 | `hsystem/sim_script/20250819TZB/sim_20250819测试用例1.py:167-176`（同 builder L209-218） |

## 附录 B：最终心智模型（20 问快速答案）

1. **胜负目标**：在首个黑舰突防（x≤50000）前击毁全部黑 USV；同时保证白方单位不全灭。
2. **为何 POMDP**：己方完全可观，敌方只通过探测（真值+30s 黏性）/被动告警（仅方位）可见，需在线推断。
3. **白方能看什么**：己方全状态 + 观测敌（真值坐标/速度）+ 奖励计数。
4. **白方绝对不能看什么**：黑方引擎内部状态/总数/脚本/固定坐标速度/engine 本体（HTTP-only）。
5. **USV=战斗平台**（锁定/击杀），**UAV=感知资产**（60km 共享探测，延长锁距，不能战斗）。
6. **combat 机制影响**：2 命中/300s/80%/冻结 → 集中火力（2v1/3v1）必胜竞速、1v1 五五开；锁断=重计时 → 必须保持 <40km。
7. **V1 控制环**：status→legal→Track→Alloc→USV FS→UAV FS→Safety→apply。
8. **V2 LLM 控制什么**：posture/focus/emergency/reserve_ratio/threat_bias/uav_mode/激进度（战略资源配置），不控制具体动作。
9. **Skill vs Prompt vs policy**：Skill=长期稳定作战知识（文件）；Prompt=每步 system prompt（Role+Skill+Schema）；policy=确定性控制器硬编码规则。
10. **LLM 不输出动作**：延迟（50×实时漂移）+token+合法性校验，异步只能做战略。
11. **async 重要**：主循环不能等 LLM；快照摘要+后台线程+600s cooldown 保证实时。
12. **fallback**：LLM_ENABLED=false → DEFAULT_INTENT=V1；API/parse 失败 → last_valid。
13. **scale-gen 已证明**：同一 skill/prompt 跨规模可运行、LLM 行为稳定、摘要/token 规模无关。
14. **还没证明**：更大规模的真实竞速胜率（30v30 实际 0/10）、对其它黑方脚本/随机路径的泛化、统计显著性。
15. **10v10 最大失败模式**：5v5 对称对杀 RNG 方差 + UAV 在交战中缺席/事后西飞出界。
16. **random waypoint 最可能破坏**：TrackManager（点外推失配）→ UAVManager（点重搜/搜索带几何）→ 分配/追击。
17. **真正 scale-agnostic**：TrackManager 动态增删、USV/UAV 状态机按 obs 遍历、ActionSafety、top-K 摘要、reserve_ratio、扇面自适应。
18. **最值得优化**：UAV RTB 缺陷、击杀竞速的 UAV 利用、30v30 火力保存、摘要威胁模型（敌 UAV vs USV）。
19. **最重要 engineering risks**：quirk 胜率失真、引擎 DB 双源、无 CI/seed、评估成本高、LLM 外部依赖。
20. **随机路径泛化需重点模块**：TrackManager 预测/不确定性、UAVManager reacquire/搜索、ThreatAllocator ETA、USVController 追击逻辑、Summary 机动信息。
