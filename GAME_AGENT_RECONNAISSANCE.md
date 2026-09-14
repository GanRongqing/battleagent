# GAME AGENT 技术侦察报告 (Technical Reconnaissance)

> 目的: 为 30v30 (15 USV + 15 UAV 对 15 USV + 15 UAV) 的 AI 对战 Agent 设计提供
> 代码级机制还原与架构建议。本报告只做代码阅读 + 短时引擎验证, **未修改 simulator / Agent, 未跑长仿真**。
>
> 侦察时间: 2026-08-09。所有结论给出 `文件 / 类 / 函数` 定位。

---

## 0. 一句话全景

这是一个**引擎以 50× 实时持续奔跑、永不等待 Agent** 的"射击后不管"仿真系统。
Agent 只能在每个宏观步 (30 仿真秒) 通过 `/apply` 注入一批动作, 其余时间全部由
引擎自主推进 (移动、锁定计时、命中、冻结、UAV 电池)。因此 Agent 设计的**第一原则**是:

> **把一切能在引擎侧自动完成的机制交给引擎, Agent 只做"宏观步级"的调度与姿态维持。**
> 锁定的 300s 计时是目标侧自主的, 只要 Agent 把攻击 USV 保持在 40km 内并**不切换目标**,
> 击杀过程完全无需 Agent 干预 —— 这是整个系统的"免费午餐"。

---

## 1. 真实游戏循环 (Real Game Loop)

### 1.1 链路

```
agent ──HTTP──► pomdp_api/main.py (:8000) ──gRPC──► base_server (:6000) ──► sim_server (:6001) ──► simulation engine
```

- `pomdp_api/main.py`: HTTP→gRPC 网关, 全部智能体可见的观测/动作/奖励都经它。
  关键函数: `_grpc_call` / `_fetch_raw_state` / `_build_obs_text` / `_build_legal_actions` / `_execute_one_action`。
- `simserver/sim_server.py:init` (L211): 读 `sces.json` 里脚本文本 → 写入 `temp.py` →
  `import temp; reload(temp); engine = temp.sim(**kwargs); engine.activate()` →
  `threading.Thread(target=engine.update)` 后台常跑 (L279-281)。
- `simserver/base_server.py:control` (L173): `flag=='simulation'` 路由到 sim_server。

### 1.2 关键: `activate()` 就是"启动" (已实测确认)

`sim_server.init` **不调用 `engine.start()`**。但经代码追踪 + 实测,
`engine.activate()` 会通过 `Entity.activate → Router.activate(self) → implement/check/start`
最终触发 `DispatchEngine.start → _starter(self)`, 即**场景里 `set_starter(start)` 注册的启动函数会执行**。
实测 (`sim_20250819测试用例1.py` + `activate()` + `update(delta=3)`):

- `put_uav_in_ship(white_uav_i, white_usv_i)` 生效: `white_uav*.is_at_home=True, home_name=white_usv*`。
- `turn_on_radars / turn_on_lockers / uavbattery.turn_on / judge.activate()` 均生效。
- 黑方 USV 沿 `cmd_sail_area` 航路点西行: `black_usv1 x: 260000 → 258800 (t=120s)`, 精确 10 m/s。
- **白方 USV 无需任何指令默认以 10 m/s 向东航行** (gen_platform 给的初始 course=90 直接进入运动),
  即"白方永远在向敌推进"是引擎默认行为。

> ⚠️ 不要在 `activate()` 之后再调 `engine.start()` —— 会二次执行 starter,
> `uavbattery.turn_on()` 触发 `assert not self._is_on` 崩溃。部署流只 `activate()`。

### 1.3 宏观步门控 (Macro-step gate)

- `/apply` 执行一批动作后设置 `release_until_time = current_time + MACRO_STEP_DURATION(30)`。
- `/status` 的 `waiting_for_command` 是**只读提醒**, 引擎不会因此暂停。
- 实测节奏: 50× 倍速下 30 仿真秒 = **0.6 秒真实时间**。

### 1.4 结束条件 (engine 侧, `tzb_engine.py:get_state` L120-135)

| 条件 | 判据 |
|---|---|
| 我方全灭 | `white_ship_alive + white_uav_alive == 0` |
| 敌方全灭 | `black_ship_alive == 0` |
| 敌方突防 | `len(judge.black_success) > 0` (黑方 USV `coords[0] <= destination(50000)`) |
| 引擎停止 | `not engine.isactive` |

### 1.5 时间线推演 (默认无人干预)

- 白 USV 东进 10 m/s, 黑 USV 西行 10 m/s → 相对闭合 **20 m/s**。
- 初始间距 260km。白 USV 雷达 35km → 首次接敌约 `(260-35)k/20 ≈ 11250s` ≈ **225s 真实 (ratio 50)**。
- 白 UAV 60km/150 m/s 若前出, 接敌更快。

---

## 2. 观测空间分析 (Observation Space)

### 2.1 接口

- `GET /obs`: 返回 PlainText 语义文本, 由 `_build_obs_text` (pomdp_api L701) 组装,
  分节 `[Info] / [我方无人艇] / [我方无人机] / [敌方情报] / [派生信号]`。
- `GET /status`: 返回结构化"资源快照" (白方 usv/uav 全状态 + 观察信息 + 奖励信号 + 行动历史) +
  `局内时间` / `已结束` / `对局结果`。**数值更密, 推荐作为 Agent 主数据源**。
- 敌方情报由 `_build_enemy_intel` (L646) 把 `white_observation` 拆成:
  - **active**: 在探测轨迹上、位置+速度已知的敌舰 (真值)。
  - **passive**: 仅"被锁定"告警, 给出敌攻击者 **名字** + 相对方位 (从 `relative_orientation`)。

### 2.2 引擎侧真值 (`tzb_engine.get_state`)

- `white_usv_states`: `position/velocity/speed/course` (真值) + `is_locked/is_locking/is_frozen/
  locked_attacker/relative_orientation/locking_unit/locked_times/uav(机库)`。
- `white_uav_states`: 动力学真值 + `battery / battery_format / is_charging / is_at_usv / home_name`。
- `black_usv_states` / `black_uav_states`: **含敌方真值 kinematics + is_frozen + locked_times**
  —— **API 层不暴露**, 详见 §7 信息泄漏。

### 2.3 敌情来源与衰减

- `white_observation` 来自 `engine.get_white_targets()` (engine.py L246):
  所有 RED 单位 `intelligence.targets` 并集 + BLUE 中 `locker.locked or frozen` 的 Ship。
  轨迹内容为**真实坐标/速度** (`_target_info['position']=list(_unit.coords)`)。
- 轨迹过期: `Intelligence._work` (intelligence.py L110) 里
  `radar_tracks = [x for x in radar_tracks if engine.tick - x.when <= 1000*radar_update_time]`,
  `radar_update_time=30` → **雷达轨迹 30s 后过期消失**。
- 探测机制 (`radar.pyx:acquire` L100-131): `detected_method=="fixed"` →
  `dis < attr.distance` 即命中, **确定性、无噪声**。UAV 扇区 `sector + heading` (±30° 前向锥)。

### 2.4 "POMDP 浓度"结论

**中等偏弱。** 我方全状态 = 真值 (完全可观); 敌情 = "有界确定性探测 + 30s 过期 +
被锁定告警(名+方位)"。**没有测量噪声、没有虚假目标、没有传感器不确定性** —— 属于
"部分可观 (敌方隐藏, 探测硬截断)" 而非经典带噪 POMDP。因此**不必上粒子滤波/信念 MDP 等重型工具**;
一个简单的"航迹表 + 过期外推"就足够支撑决策。

---

## 3. 动作空间分析 (Action Space)

### 3.1 五类动作 (`_build_legal_actions` pomdp_api L867)

| 类型 | 作用对象 | 约束 | 引擎侧函数 |
|---|---|---|---|
| `move` | 白 USV | speed∈[0,20], course∈[0,360] | `send_command` → `MotorTZB.set_target_speed/angle` |
| `lock` | 白 USV × 可见敌舰 | 见 §4 | `cmd_lock` |
| `launch_uav` | 白 USV×其机库 UAV | UAV 在机库 | `cmd_uav_takeoff` |
| `fly` | 空中白 UAV | speed∈[0,150], course | `send_command` |
| `land_uav` | 空中 UAV × USV | 距离<10km 且 speed<100 | `cmd_uav_land` (API 端 >5m 会引导飞行) |

### 3.2 30v30 规模实测估算

| 动作类 | 数量 (15 USV + 15 UAV) |
|---|---|
| move | 15 |
| lock | 15 (USV) × 当前可见敌舰 (最多 15) = **≤225** |
| launch_uav | ≤15 |
| fly | ≤15 (空中 UAV) |
| land_uav | ≤15 (UAV) × ≤15 (USV) = **≤225** |
| **合计** | **≤~495 条** |

每条动作文本 ~40-60 字符 (含中文动词), 全量 `/legal_actions` 在满可见时约
**2.5万~3.5万字符 ≈ 8k~15k token** (中文 token 单价高于英文)。`/obs` 全量约 5k~10k token。
**一个完整决策上下文 (obs + legal + prompt) 在 30v30 时约 15k~30k token** —— 这是 §10 的核心瓶颈。

### 3.3 动作语义陷阱

- `lock` 目标必须是当前"可见"的 (`target in white_targets`); 重新锁定已锁目标是**幂等跳过** (API 返回 `skipped=True`), 安全。
- `land_uav`: 条件苛刻 (距离<10km 且 UAV speed<100)。API 端对 >5m 的目标 USV 做引导飞行,
  所以**只要在 10km 内 + 先减速, 降落可以自动引导**。
- 无人机 1:1 配属 (white_uav_i ↔ white_usv_i), 但**可以跨母船降落/起飞** (land 的目标 USV 不限制为原母船)。

---

## 4. 锁定/攻击 FSM 详解 (Lock / Attack FSM)

### 4.1 建立锁定

`engine.cmd_lock` (engine.py L285) 要求:
1. 攻击者/目标都是 Ship; 不同阵营; 攻击者必须 RED;
2. 目标在 `get_white_targets()` (必须可见);
3. `distance < 40_000` (40km);
4. `target.locker.is_locked(attacker)` 且 `attacker.locker.is_locking(target)` (一船一锁, 锁中不可切换)。

### 4.2 计时与命中 (核心机制, `arsenal/locker.py`)

- `Locker.dis=40000`, `period=1s`。`is_locked(unit_name)` (L66) 在**目标侧 locker**
  创建 `locked_info[attacker] = {locked_begin_time, locked_times:0, frozen:False, ...}`。
- **计时器跑在"目标"的 locker 上, 一旦建立即自主运行, 与 Agent 是否重复发锁无关。**
- `_locked_work` (L92, 目标侧):
  - `dist >= 40km` → `locked=False` (链路断开, 计时作废; 重新锁定则重建并重计时);
  - `engine.time - locked_begin_time > 300` → 命中判定 `random.random() > 0.2` (即 **80% 命中**);
    命中则 `locked_times += 1; frozen=True` (冻结 300s);
  - `locked_times >= 2` → `self.home_unit.kill()` (**累计 2 次命中击沉**), 母船沉没连带击毁机载 UAV。
- 冻结期间: motor 冻结 + 雷达关 + locker 关 (但保留 WORK 态); 300s 后解冻恢复。
- 多个敌 USV **可同时锁定同一目标** (各自独立 `locked_info` 条目); 单个 USV 只能锁 1 个目标。

### 4.3 回答核心问题: **300s 锁定会被重规划打断吗? —— 不会。**

- 计时器在目标侧自主运行,**不依赖 Agent 每步重发锁**。Agent 全程发 noop,
  只要攻击 USV 一直待在 40km 内、目标未沉没, 300s 后照样命中。
- `/apply` 重复发 lock 被跳过 (安全), **不会重置计时器** (`locked_begin_time` 只在 `is_locked`
  首次创建时写入; 重复 `is_locked` 返回已有条目)。
- **会打断 300s 的三个条件**: (a) 攻击 USV 离开 40km (锁断, 重锁重计时);
  (b) 目标沉没; (c) 目标被冻结后雷达/锁定关机, 且攻击侧 `_locking_work` 因距离或 2 次命中清锁。
- **Agent 的关键职责**不是"持续发锁", 而是"**把攻击 USV 保持在 40km 内并保持目标在可见轨迹上**",
  以及"**锁定期间绝不切换目标**" (`is_locking` 在切换时返回 False, 直接拒绝)。

### 4.4 黑方镜像

`engine.black_cmd_lock` (L321) 完全镜像; 场景里 `black_strategy` (sim 脚本 L167) 每秒对所有可见白 USV 发锁。
**敌方会无脑锁定任何进入其 40km / 可见范围的白 USV** —— 白方保命 = 不要停在黑 USV 40km 内被锁。

---

## 5. UAV 生命周期 (UAV Lifecycle)

### 5.1 状态机 (`arsenal/platform.py` Plane + `arsenal/uavbattery.py` UavBattery)

```
机库(is_at_home, 雷达关, 充电中) ──cmd_uav_takeoff──► 飞行(雷达开 ±30°扇区60km, 电池1:1消耗)
      ▲                                                    │
      └──────────── cmd_uav_land (<10km 且 speed<100) ◄─────┘
```

- 起飞 (`Plane.take_off` L213): `isdetectable=True, charging=False, is_at_home=False`,
  `motor.remove_home()`, 设目标航向/速度, `take_off_time = engine.time`。
- 电池 (`UavBattery._battery_work` L67):
  `fly_time_remain = total_fly_time(25000) - (engine.time - take_off_time)`; **`<0 → kill()`。无自动返航!**
- 降落 (`Plane.land` L234): 回到母船 `planes` 列表, `set_at_home`, 雷达关, `is_at_home=True`,
  之后按 `charge_rate = 25000/18000 ≈ 1.39` (充电 1 秒补 ~1.39 飞行秒) 回电。
- 若母船被击沉 → 机载 UAV 连带死亡 (`Ship.kill` 击杀 onboard plane)。

### 5.2 三个对 Agent 致命的点

1. **无自动返航**: 电量耗尽直接死。UAV 续航 25000s 飞行 (~7 小时), 但**起飞即消耗**,
   Agent 必须管理"侦察往返"。低频巡检 + 定时回充是必须的。
2. **降落门槛高**: 需 <10km 且 speed<100。跨母船降落可行 (任何白 USV 均可接收)。
3. **UAV 不会被锁定/击毁**: Plane 没有 locker, 武器只锁 Ship。UAV 唯一死亡来源 = 电池耗尽 / 母船沉没。
   所以 UAV 是**安全的侦察资产**, 可以放心前出 (只要管好电)。

---

## 6. 现有 Agent 分析 (Existing Agents)

| 文件 | 风格 | 通用性 (30v30) | 可复用件 |
|---|---|---|---|
| `agent_llm.py` | DeepSeek 纯 LLM, 全公平观测 | ✅ 无 BLACK_Y 硬编码 | `call_deepseek`(thinking disabled)、`parse_actions`(正则容错)、主循环骨架 (start→obs+legal→LLM→apply)、5 条优先级提示词 |
| `agent_defense.py` | 规则防守 | ❌ 硬编码 `BLACK_Y` 5 船坐标 | **带控 (SAFE_MIN/MAX)、nearest_target 分配、UAV 充电循环 (低电量返航→<8km降落→≥90%再起飞)、单船单锁、被锁后撤** |
| `agent_attack.py` | 规则激进 | ❌ 同上 | 前出距离调节思路 |
| `agent_win.py` | v7 获胜脚本 | ❌ 同上 | 锁定节奏 (LAUNCH_STEP 式分批)、击杀判据 |
| `agent_recon.py` / `agent_test.py` | 早期变体 | ❌ | 观测解析示例 |

- **agent_llm 的问题**: 提示词仍写"5艘USV和5架UAV"; 每宏观步一次 LLM 调用,
  50× 倍速下真实延迟 10-30s = 500-1500 仿真秒漂移 → **30v30 下不可行** (见 §10)。
- **agent_defense/attack/win 的问题**: `BLACK_Y` 是**针对 5 船场景的位置先验 (作弊级硬编码)**,
  15+15 布局完全不同 (y=300000~510000 间隔 15000), 直接失效。但其**控制模式本身正确**,
  是本报告推荐 MVP 的直接素材。

---

## 7. 作弊 / 信息泄漏清单 (Cheating / Info Leakage)

| 级别 | 泄漏点 | 位置 | 说明 / 处置 |
|---|---|---|---|
| **L1 真泄漏** | `black_usv_states`/`black_uav_states` 含敌方真值 (位置/速度/冻结/锁定次数); `num_black_*` | `tzb_engine.get_state` L33-44 | **API 层已隐藏** (pomdp_api 只转发白方+白观)。但 gRPC 原始通道可拿到 —— 部署时不要开放 gRPC, 只走 HTTP。 |
| **L2 场景先验** | `BLACK_Y = {...}` 硬编码 5 船 y 坐标 | agent_defense/attack/win | 对指定场景是"作弊"; 且 15+15 失效。**必须删除**。 |
| **L3 边界公平** | `white_observation` 给出的敌方位置是**无噪声真值** (确定性 `fixed` 探测) | radar.pyx / engine.get_white_targets | 设计如此 (任务给的"雷达捕获")。可接受, 但注意 30s 过期 = 信息时效性差。 |
| **L4 敌方身份泄漏** | "被锁定"告警带攻击者**名字** (`emy_name`) | pomdp_api `_build_enemy_intel` | 名字可反查敌方存在性; 结合 active 航迹可推断敌编队编号。轻微。 |
| **L5 幽灵被锁** | `Locker.emy_name` **只增不删** | locker.py `is_locked` | 锁定结束后"被锁定"仍显示旧攻击者 → Agent 会误后撤/误回充。**是 Agent 端的观测 bug 源**, 处理: 结合 `locked` 标志判断真实被锁。 |
| **L6 场景文件** | `任务区域.json` 八边形区域坐标 | sim_script/.../Demo | 是公开场景配置, Agent 作者天然知道防线 x≤50000。不算泄漏。 |

> 结论: 走 HTTP API 的 Agent **只能拿到公平观测**; 唯一隐患是 L4 (名字) 与 L5 (幽灵被锁)。
> L5 必须在 Agent 层修复 (以 `locked` 布尔为准, 不信任 `locked_attacker` 列表长度)。

---

## 8. 最佳 Agent 架构 (Best Architecture)

### 结论: **层次化混合架构 (Hierarchical Hybrid)**

```
┌─────────────────────────────────────────────────────────────┐
│  LLM Commander (低频, 每 300~600 仿真秒)                      │
│  读"聚合摘要"(不是全量obs), 定战略目标: 推进扇区/目标优先级/    │
│  是否动用UAV前出/整体攻防姿态。输出结构化指令(JSON)。          │
├─────────────────────────────────────────────────────────────┤
│  规则控制器层 (每个宏观步 30s 运行, 确定性)                    │
│  ├─ USV 控制器: 带控(30-38km)、向敌推进、被锁后撤、冻结规避    │
│  ├─ 锁定调度器: Hungarian 最优分配 USV↔目标 (锁最划算的敌舰)   │
│  ├─ UAV 控制器: 起飞调度、巡逻航点、低电回充、<10km降落+引导    │
│  └─ 安全层 (最高优先级): 被锁→后撤; 冻结→散开; 电池<20%→强制RTB │
├─────────────────────────────────────────────────────────────┤
│  动作构建器: 控制器输出→/legal_actions 校验→去重→/apply        │
└─────────────────────────────────────────────────────────────┘
```

**为什么**:
- **纯 LLM (agent_llm 式)** 无法稳定获胜 —— 每宏观步一次调用在 30v30 下 token+延迟双重不可行 (见 §10)。
- **纯规则 (agent_defense 式)** 可以赢, 但没有"LLM/Agent 叙事", 且对场景变动脆弱。
- **混合**: 确定性机制 (锁定计时、电池、带控) 交给规则层 (便宜、可靠、每秒可跑),
  LLM 只在关键节点做"策略"决策 (低频、读摘要、输出目标级指令), 既省钱又满足"AI Agent 叙事",
  也天然泛化到任意兵力规模 (不依赖 BLACK_Y)。

### 关键设计点

1. **观测聚合**: Commander 不看 15k token 的全量 obs, 而看控制器聚合的 10 行摘要
   (敌编队质心/数量/威胁度、我方存活/锁定/电量分布、推进进度)。token 从 ~20k 降到 ~2k。
2. **锁定靠"保持"不靠"重发"**: 锁定调度器只决定"谁锁谁", 一旦锁上,
   规则层只负责把攻击 USV 钉在 40km 内, 300s 计时完全交给引擎。
3. **保命是硬约束**: 安全层永远优先于任何策略输出 (被锁即撤, 无论 LLM 想不想进攻)。

---

## 9. 游戏 AI 技术评估 (低代价高收益)

| 技术 | 收益 | 代价 | 建议 |
|---|---|---|---|
| **FSM (有限状态机)** | 高 | 低 | ✅ 引擎本身就是 FSM; 控制器直接用状态机 (待命/接敌/锁定/撤退/回充) |
| **带控 + 距离维持 (band control)** | 高 | 低 | ✅ 复用 agent_defense 的 SAFE_MIN/MAX 模式 |
| **Hungarian 最优分配** (USV↔目标) | 高 | 低 | ✅ `scipy.optimize.linear_sum_assignment`, 15×15 秒算; 避免 3 条 USV 抢 1 个目标 |
| **黑板 (blackboard)** | 中 | 低 | ✅ 用 /status 快照 + 自建"航迹表"当黑板, 控制器共享 |
| **航迹/信念外推 (belief tracking)** | 中高 | 中 | ✅ 维护 {目标: pos, vel, last_seen}; 轨迹过期后按匀速外推 30s, 填补雷达过期窗口 |
| 效用函数 (utility) | 中 | 低 | 可选, 用于 UAV 回充优先级排序 |
| Behavior Tree | 中 | 中 | 跳过 —— 领域足够确定, FSM 够用 |
| 多智能体 LLM (每单位一个 LLM) | 低 | 高 | ❌ token 爆炸 + 协同脆弱 |
| 蒙特卡洛 / 搜索 | 低 | 高 | ❌ 仿真含随机命中且不可回放, 搜索无意义 |
| RL | 中 | 极高 | ❌ MVP 不上 (需奖励塑形+数千局, 无基建) |

**MVP 只上**: FSM + 带控 + Hungarian + 黑板 + 简单外推 + (可选) LLM Commander。

---

## 10. 30v30 可扩展性分析 (Scalability)

### 10.1 Token 增长 (实测/估算)

| 项 | 5v5 (现状) | 30v30 |
|---|---|---|
| `/obs` | ~1-2k token | **5-10k** (30 白单位 + 敌情) |
| `/legal_actions` | ~1-2k (≤55 条) | **~8-15k** (≤495 条) |
| 单次决策上下文 | ~3-5k | **15-30k** |
| LLM 输出 (max_tokens) | 2k | 2k (动作仍由规则层生成, LLM 只出指令) |

### 10.2 延迟 vs 仿真漂移 (致命问题)

- 引擎 50× 实时、**永不等待**。LLM 一次调用 (flash, max_tokens=2000) 真实延迟 ~10-30s
  = **500-1500 仿真秒漂移**。期间敌舰以 10 m/s 推进 5-15km, 我方默认东进同理。
- 黑方 USV 10 m/s、白 USV 10 m/s, 40km 锁定窗内漂移 1s 就会把攻击 USV 推出 40km → 锁断重计时。
- **结论: 每宏观步全量 LLM 决策在 30v30 下不可行。**

### 10.3 控制频率推荐

| 层 | 频率 | 说明 |
|---|---|---|
| 规则层 (USV/UAV/锁定) | 每宏观步 (30 仿真秒 = 0.6s 真实) | 每步 HTTP 开销 ~几十 ms, 无压力 |
| LLM Commander | **每 300-600 仿真秒** (≈6-12s 真实) | 与 LLM 延迟匹配; 只在重大事件/周期性节点触发 |
| 安全层 | 每宏观步 | 硬约束, 最高优先 |

若必须提升 LLM 决策频率: 需把 `sim_20250819测试用例1.py` 的 `set_ratio(50)` 降到 10-20
(1 次 LLM 调用漂移 = 100-600 仿真秒) —— 属 **P0 配置改动**。

### 10.4 机制自洽性检查

- 锁定 300s 自主计时 → 与 Agent 频率无关, 规则层只需低频维持距离。✅
- UAV 电池 25000s → 只要调度得当, 30 架 UAV 可滚动侦察; 无自动返航是唯一风险点。⚠️
- 黑方每 1s 无脑锁定可见白 USV → 白方任何停在黑 40km 内且被黑的单位会被快速锁上。⚠️

---

## 11. 最小可行 MVP 架构 (Minimal MVP)

### 11.1 组件与职责 (新增文件建议在 `/root/autodl-tmp/hsystem/agent_sdk/` 或 `simserver` 旁)

| 组件 | 文件 | 职责 | 复用 |
|---|---|---|---|
| 状态解析器 | `game_state.py` | GET /status + /obs → 结构化 dict; 修 L5 (以 `locked` 判真实被锁) | 解析逻辑仿 agent_defense |
| 航迹/信念表 | `tracks.py` | {目标:pos,vel,last_seen}; 过期外推; 供锁定调度 | 新写, 轻量 |
| USV 控制器 | `controllers/usv_ctl.py` | 带控 (30-38km)、被锁后撤、冻结散开、向敌推进 | 复用 agent_defense 带控 |
| 锁定调度器 | `controllers/lock_ctl.py` | Hungarian 分配 USV↔可见目标; 维持 40km | 新写 + scipy |
| UAV 控制器 | `controllers/uav_ctl.py` | 起飞/巡逻/低电回充/引导降落 | 复用 agent_defense 充电循环 |
| 安全层 | `controllers/safety.py` | 最高优先级硬约束 | 仿 agent_defense 保命 |
| LLM Commander | `commander.py` | 每 300-600s 读摘要 → 战略指令 (JSON) | 复用 agent_llm `call_deepseek/parse_actions` |
| 动作构建器 | `action_builder.py` | 控制器+指令 → 动作列表 → /legal_actions 校验 → 去重 → /apply | 复用 agent_llm 主循环 |
| 主循环 | `agent_main.py` | /start → 循环 → 结束判定 | 复用 agent_llm 主循环 |

### 11.2 复用清单 (Top 现有资产)

1. `agent_defense.py` — 带控 + UAV 充电循环 + 被锁后撤 (去 BLACK_Y)。
2. `agent_llm.py` — `call_deepseek` (thinking:disabled) + `parse_actions` + 主循环。
3. `pomdp_api` `/status` 资源快照 — 已是结构化, 免解析。
4. `pomdp_api` `/legal_actions` — 动作空间校验/去重的唯一权威来源。
5. `sim_20250819测试用例1.py` — 15+15 场景 (starter/manipulator/裁判均已验证可用)。

### 11.3 必须的改动 (P0/P1/P2)

**P0 (能跑、能赢 15+15):**
1. 删除所有 `BLACK_Y` 硬编码 → 动态 nearest/Hungarian 分配。
2. 规则层四件套 (usv_ctl / lock_ctl / uav_ctl / safety) + 动作构建器。
3. UAV 无自动返航的 Agent 侧兜底 (低电强制 RTB) —— 引擎不改, Agent 管。
4. 修正 L5 幽灵被锁 (以 `locked` 为准)。

**P1 (稳定、加智能):**
5. LLM Commander 接入 (聚合摘要 + 每 300-600s 战略指令)。
6. 航迹外推填 30s 过期窗口; 被锁告警(名字+方位)与航迹融合。
7. (可选) 调低 `set_ratio` 到 10-20 或改造为事件驱动, 提升决策密度。
8. 参数调优: 带控宽度、回充阈值、UAV 巡逻深度。

**P2 (锦上添花):**
9. 多阶段战术 (侦察→接敌→收割→清尾), 多指挥位。
10. 主动电子战行为 (UAV 前置侦察编队), 冻结期目标再分配。
11. 可选 RL/搜索 实验基座 (回报从 `/result` 奖励信号取)。

### 11.4 风险与待验证项

- [ ] **首次全链路验证 (P0 起步前必做)**: 起 sim_server 后走一遍 `/start → /obs → /legal_actions → /apply`,
      确认 30v30 下 HTTP 层不再报错 (任务 #6 未在本轮完成)。
- [ ] 白 USV 默认东进 10 m/s 与规则层带控的冲突 (控制器应显式覆盖, 不要依赖默认)。
- [ ] 冻结 (frozen) 期 300s 的"雷达关 + 锁定关": 冻结目标从白方航迹消失 → 锁定调度需在解冻前
      重新分配或保持 (已锁的 USV 在目标冻结期间继续等待, 解冻后自动续上 300s 需重新锁定)。
- [ ] `任务区域.json` 的边界问题已实测**非致命** (activate 时 motor 把船推离边界 ~1m, 首判 contains=True),
      但**非常脆弱** —— 建议后续把白方初始 x 从 0 改到 >0 (如 500), 彻底消除隐患。

---

## 附录 A: 本轮实测记录 (engine-only, 无服务器/无长仿)

| 测试 | 结果 |
|---|---|
| `activate()` 后 starter 是否执行 | ✅ `put_uav_in_ship` 生效 (is_at_home=True, home_name=white_usv*); 黑 USV 西行 10 m/s 精确 |
| 白 USV 默认行为 | ✅ 无指令自动东进 10 m/s |
| manipulator 调度 | ✅ 自定义每秒 probe 31 次/30s |
| judge 是否击杀边界单位 | ✅ 61 次 _judge 运行, 15/15 存活 (t=0 时 x 已=1m 离开边界) |
| judge area contains | `contains((0,300000))=False`, `contains((0,300001))=True` (边界仅一线之差) |
| UAV 机库电池 | ✅ is_at_home=True, charging=False, 电量=25000 (满) |

## 附录 B: 关键文件索引

- `pomdp_api/main.py` — HTTP 网关 (MACRO_STEP_DURATION=30; _build_obs_text L701; _build_legal_actions L867; _execute_one_action L1050)
- `simulation/core/tzb_engine.py` — `get_state` (白方真值 + 黑方真值被 API 隐藏) / `send_command`
- `simulation/core/engine.py` — `cmd_lock` L285 / `get_white_targets` L246 / `cmd_uav_takeoff` L352 / `cmd_uav_land` L363
- `simulation/arsenal/locker.py` — `Locker` (dis=40000, period=1; `_locked_work` L92: 300s→80%命中→冻结→2次击杀)
- `simulation/arsenal/platform.py` — `Plane.take_off` L213 / `land` L234; `Ship.load_uav`
- `simulation/arsenal/uavbattery.py` — `UavBattery` (25000/18000/charge_rate≈1.39; `<0→kill`, 无自动返航)
- `simulation/arsenal/radar.pyx` — `acquire` L100 (fixed→距离硬截断; UAV ±30°扇区)
- `simulation/arsenal/intelligence.py` — 轨迹 30s 过期 (radar_update_time=30)
- `simserver/sim_server.py` — `init` L211 (activate + 后台 update) / `control` L94
- `sim_script/20250819TZB/sim_20250819测试用例1.py` — 15+15 场景 (NUM_UNITS=15; starter L154; black_strategy L167; set_ratio(50))
