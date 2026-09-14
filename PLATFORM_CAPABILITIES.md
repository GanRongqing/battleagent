# PLATFORM CAPABILITIES SPECIFICATION — 平台能力规格说明

> **本轮目标**: 在实现最终白方 Agent 之前, 把 USV 与 UAV 的**真实能力边界、控制命令、传感器语义**完整确认。
> 方法: 只读源码 (`pomdp_api/main.py`, `simulation/core/{tzb_engine,engine}.py`, `simulation/arsenal/*`,
> 官方场景 `sim_20250819测试用例1.py`) + **短 probe** (位于 `probe_rules/`, 全部秒级)。
> **未修改任何代码 / simulator, 未跑长仿真**。探测时间 2026-08-09。
>
> 所有数值均给出 `file:line`; 标 "实测" 的为探针直接测量结果。

---

## ⚠️ 相对前两份报告的三处修正 (先读)

1. **舰船转弯近似瞬时, 不是 5°/s。** 前报告依据 `motor.json` 的 `max_angle_velocity=5`(标注"角度制")
   推得"180° 需 36s"。实测 `probe_cap_turn9` 中 90° 转向仅造成 **~1m 位移 (≈0.1s, 1 tick)**;
   `probe_cap_turn8` 中 180° 转向同样瞬时完成。代码层原因: `tzb_motor.py:84-93` 把 `max_angle_velocity*period`
   当作**弧度**阈值 (5×0.1=0.5 rad/tick ≈ 286°/s), 且编译后的 `.so` 实测更快。
   → **Agent 可以认为转向零代价, 航向指令立即生效。**

2. **白 USV 有效最大速度 = 20 m/s (不是 10)。** `simulation/database/json/motor.json` 写 `max_speed:10`,
   但引擎运行时 DB (`base_engine.pyx:482` 用默认 `cache=True` 加载 `cache_json.pkl`) 中为 **20**,
   与 `probe_cap_speed` 实测 (10→20 加速, 30s 位移 576m, 精确吻合) 一致。
   → 白 USV 巡航 20 m/s, 比敌方 10 m/s 快 2 倍。

3. **敌方情报黏性 = 30s (不是 5s)。** `intelligence.json` 写 `radar_update_time:5`, 但引擎实际加载
   的模型是 `QB` (`intelligence.py` 组件 `model='QB'`, 实测 `probe_intel_src`), 其 DB 值 `radar_update_time=30`。
   实测 `probe_cap_sense2/P1`: UAV 转离目标后, `white_targets` 中目标 **~25-35s 后才消失**。
   → 探测航迹在目标脱离雷达后仍对全白方可见约 30s (给 Agent 留了外推/决策窗口)。

其余结论均与 `GAME_AGENT_RECONNAISSANCE.md` / `GAME_RULES_AND_WINNING_STRATEGY.md` 一致。

---

## 1. USV 无人艇能力

### 1.1 机动 (Movement)

| 项 | 值 | 依据 |
|---|---|---|
| 机动组件 | `ShipMotorTZB` (class `MotorTZB`) | `sim_20250819测试用例1.py:78`; `simulation/database/json/motor.json` |
| 位置更新周期 | **0.1s** | `motor.json` `ShipMotorTZB.period=0.1` |
| 最大速度 | **20 m/s** (实测; 引擎 DB 值) | `probe_cap_speed`; `cache_json.pkl`; 见修正 #2 |
| 加速度 | **2 m/s²** (max_acce) | `motor.json`; `tzb_motor.py:100-103` (每 tick `±max_acce*period=0.2 m/s`) |
| 转向 | **近似瞬时** (实测 ≤0.15s) | `probe_cap_turn9/turn8`; `tzb_motor.py:84-93` 见修正 #1 |
| 指令持续性 | **持续** — 一旦给定 `target_speed/target_course`, 无条件一直执行到新指令 | `send_command`→`set_target_speed/angle` (`tzb_engine.py:151-169`); `tzb_motor.py:40` |

**指令执行链** (`send_command`, `tzb_engine.py:151-169`):
只对 RED 单位、只对 `MotorTZB`; `target_speed<0` 或 `target_course∉[0,360]` 直接拒绝;
否则 `unit.motor.set_target_speed(target_speed); unit.motor.set_target_angle(target_course)`。

**worked example (实测数值)**:

```
command:   white_usv1 移动 target_speed=20 target_course=90        (t=0 宏步)
internal:  motor.target_speed=20  target_angle=90°(1.5708rad)
           real_speed=10 (场景初速, sim脚本:83 gen(...,10,90)) → 以 2 m/s² 爬升
           real_angle=90° (无需转向, 瞬时对准)
30s later: real_speed=20; 位移 ≈ +575m 东 (加速段75m + 匀速段500m, probe_cap_speed: 576m)
           y 不变; course=90; 指令仍持久有效
300s later: real_speed=20; 位移 ≈ +5975m 东 (加速段75m + 295s×20m/s=5900m)
            y 不变; 命令未被重置, 继续巡航
```

> 推论: 白 USV 相对黑船 (10 m/s 西行, sim 脚本:124-129) 的**相对闭合速度可达 30 m/s**。
> 初始 260km 间距, 纯靠 USV 最快约 `260km/30 ≈ 8667s ≈ 2.4h` 接敌; UAV 前出可大幅提前 (见 §2)。

### 1.2 雷达

| 项 | 值 | 依据 |
|---|---|---|
| 型号 | `RadarWithGuider` | `sim:78`; `radar.pyx:619` |
| 探测距离 | **35,000 m** | `sim:71` (`engine.db["RadarWithGuider"]["distance"]=35_000`) |
| 扇区 | **[0,360] 全向** | `sim:72` |
| 扫描周期 | 2s (`period=2`, `yield_time=2`, `update_time=2`) | `radar.json` |
| 探测模型 | `detected_method="fixed"` → **确定性、无噪声**: 距离+高度+扇区命中即建航 | `sim:73`; `radar.pyx:83-131` (`acquire`), `radar.pyx:270-313` (`_detect`) |
| 高度约束 | `z∈[0,10000]` | `radar.pyx:acquire` |

**建航 → 情报链**: 每次 `_detect` (2s) 把可见目标写入雷达航迹; 雷达在目标最后一次被探测后
保留航迹 **2s** (`radar.pyx:307-308` `tick - m_track.when <= 1000*update_time`), 随后移出
`_found_target_tracks`; 但白方情报表 `white_targets` 还会因 **30s 情报黏性** 继续保留该目标 (§3)。

### 1.3 战斗 (锁定 / 攻击)

攻击能力 = 锁定 + 自主计时命中, 全部由 `Locker` 实现 (`arsenal/locker.py`)。

**建立锁定** — `engine.cmd_lock` (`engine.py:285-320`):
1. 攻击者/目标都是 `Ship`, 不同阵营, 攻击者必须 RED;
2. 目标必须在 `get_white_targets()` 中 (可见, 见 §3);
3. `distance < 40_000` (40km);
4. **一船一锁**: `target.locker.is_locked(attacker)` 首次建立 `locked_info[attacker]`;
   `attacker.locker.is_locking(target)` 若已锁他船 → 拒绝 ("不可切换", `engine.py:318`)。

**计时与命中** (跑在**目标侧** locker, 一旦建立即自主, 与 Agent 是否重复发锁无关):
- `_locked_work` (`locker.py:92-147`), 每 1s 周期:
  - `dist >= 40km` → 该链 `locked=False` (断开; 重锁重建并重计时) `locker.py:97-100`;
  - `engine.time - locked_begin_time > 300` → **命中判定 `random.random() > 0.2` (即 80% 命中)**,
    命中则 `locked_times += 1; frozen=True` (冻结) `locker.py:102-109`;
  - `sum(所有链 locked_times) >= 2` → **击沉** `self.home_unit.kill()`, 连带击杀机载 UAV
    (`_plane.kill()`) `locker.py:112-118`;
- **冻结 (frozen) 300s**: `motor.set_frozen()` 停船 + `radars[0].turn_off()` 雷达关机 +
  locker `_turn_off()` `locker.py:128-136`; 300s 后自动解冻恢复。
- 多艘 USV **可同时锁定同一目标** (各一条独立链); 单 USV 只能锁 1 个目标。

**实测 (probe_cap_sense2/P2)**: `w1`(31.6km) + `w2`(34.6km) 同时锁 `b1`, 链数=2;
UAV 转离使 `b1` 脱离雷达后两条锁链依旧推进; **+300s 时累计命中 2 次 → b1 被击沉**。
即 **2 USV 同锁 1 目标, 300s 内即可击杀 (双链双掷)**。

### 1.4 无人机搭载 (UAV 母船)

| 项 | 值 | 依据 |
|---|---|---|
| 机库容量 | **每 USV 最多 1 架 UAV** | `platform.py:89-94` (`Ship.load_uav`: `if self.planes: return False`) |
| 初始配属 | `white_uav_i ↔ white_usv_i` (1:1), 由 `put_uav_in_ship` 完成 | `sim:163-164`; `engine.py:376-392` |
| 起飞 | 清空母船 `planes`, UAV 置为空中 (`Plane.take_off`) | `platform.py:213-232` |
| 降落 | 任何同阵营 USV 均可接收 (**不限原母船**) | `engine.py:363-374`; `platform.py:234-246` |
| 母船被击沉 | 机载 UAV 连带死亡 | `locker.py:113-118` |

**"225 land_uav" 的含义**: `/legal_actions` 的 `[land_uav]` 组为 **每架空中的 UAV × 每个存活的 USV**
各生成一条降落指令 (`main.py:915-928`), 即 15×15 = **225 条**。同理 `[lock]` 组为
15 USV × 当前可见敌舰 (≤15) = 至多 225 条 (`main.py:896-904`)。这是 `30v30` 下
`/legal_actions` 动辄 ~500 条、2.5万+ 字符的来源。

---

## 2. UAV 无人机能力

### 2.1 机动 (Movement)

| 项 | 值 | 依据 |
|---|---|---|
| 机动组件 | `PlaneMotorTZB` (class `MotorTZB`) | `sim:91`; `motor.json` |
| 位置更新周期 | 0.1s | `motor.json` |
| 最大速度 | **150 m/s** (场景覆盖) | `sim:90` (`engine.db["PlaneMotorTZB"]["max_speed"]=150`) |
| 加速度 | **10 m/s²** | `motor.json` |
| 转向 | 近似瞬时 (同 §1.1, 相同 MotorTZB 逻辑) | `tzb_motor.py:84-93` |
| 指令持续性 | 持续 | `tzb_engine.py:151-169` |

**⚠️ 航向 = 速度方向**: `Plane.heading` = `course` (`platform.py:82-87`);
`motor.course` 在 `speed==0` 时冻结在 `_prev_course` (初始 0=北, `arch.pyx:1051`)。
→ **悬停的 UAV 雷达楔形扇区冻结在最后航向**; 要扫描必须飞起来 (实测, probe_v4/v5)。

**worked example**:
```
command:  white_uav1 飞行 target_speed=150 target_course=90     (t=0)
internal: real_speed: 0→150 以 10 m/s² 爬升 (15s 达速)
          航向即时=90° → 雷达扇区 [60,120]
30s later: 位移 ≈ 150×30 ≈ 4500m (加速段已含); 扇区指向东
300s later: 位移 ≈ 4.4km + 150×270 ≈ 44.9km; 电池消耗 300s (§2.3)
```

### 2.2 雷达

| 项 | 值 | 依据 |
|---|---|---|
| 探测距离 | **60,000 m** | `sim:87` |
| 扇区 | **[-30,30] 前向楔形, 锚定航向** | `sim:88`; `radar.pyx:83-131` (`sector + unit.heading`) |
| 周期/建航/过期 | period=2, yield=2, update=2 (同 USV) | `radar.json` |
| 探测模型 | `fixed` 确定性 | `sim:89` |

UAV 是唯一能从 **60km + 前向窄锥** 探测的资产 → 需主动控制航向做扇面扫描。
黑方 UAV 同参数 (`sim:132-134`), 即敌我对称。

### 2.3 电池 (Battery)

| 项 | 值 | 依据 |
|---|---|---|
| 总飞行时长 | **25,000s (≈6.9h 仿真)** | `database` `UAV_Battery.total_fly_time=25000`; `uavbattery.py:21` |
| 总充电时长 | 18,000s; 充电速率 **≈1.389 飞行秒/充电秒** | `uavbattery.py:29` (`total_fly_time/total_charge_time`) |
| 消耗模型 | **线性、仅按时间**, 与速度/机动无关 | `uavbattery.py:70` (`fly_time_remain = total_fly_time - (time - take_off_time)`) |
| 耗尽 | `fly_time_remain < 0` → `home_unit.kill()` (**无自动返航!**) | `uavbattery.py:71-72` |
| 充电条件 | 必须在机 (`is_at_home`) 才充电 | `uavbattery.py:58-64, 73-79` |

**实测 (probe_cap_sense/P3)**: 起飞后 100s → `fly_time_remain=24900` (精确线性);
人为置 `take_off_time` 使余量 <0 → 下一 tick **UAV 直接死亡** (`alive=False`)。
→ **Agent 必须自主管理"返航回充"**, 引擎没有任何兜底。

### 2.4 起飞 / 降落

| 项 | 条件 | 依据 |
|---|---|---|
| 起飞 `launch_uav` | UAV 在母船机库 (`uav in home.planes`) | `platform.py:213-232`; `engine.py:352-361` |
| 起飞后 | 雷达开、`is_at_home=False`、按给定 speed/course 飞行、`take_off_time=now` | `platform.py:219-229` |
| 降落 `land_uav` | 同阵营; **`dist < 10000` 且 UAV `speed < 100`** | `engine.py:363-374` |
| 降落目标 | **任何存活白 USV** (不限母船) | `engine.py:365-368` |
| API 自动引导 | 距离 >5m 时, API 自动计算方位并以 `speed=50` 引导 UAV 靠近后再降落 | `main.py:1149-1170` (`LANDING_RADIUS=5`, `main.py:85`) |

**实测 (probe_cap_land)**: `wuav1` 从 `w1` 起飞 30s (距 `w2` 8.9km, speed=50),
`cmd_uav_land('wuav1','w2')` → **True**, 非母船 `w2` 机库接收, 雷达随之关机、`is_at_home=True`。
`probe_cap_sense/S4` 也确认: 若 UAV 仍以 speed=150 抵近, `cmd_uav_land` 会因 `speed>=100` 失败 —
但 API 的引导飞行会在接近时把速度压到 50, 所以**只要目标 USV 在 10km 内, land_uav 就能自动收机**。

---

## 3. 共享感知语义 (Shared Sensing Semantics)

### 3.1 完整调用链

```
USV 雷达 (35km 全向) ──┐
                       ├─► 各 RED 单位 intelligence.radar_tracks ──► intelligence.targets
UAV 雷达 (60km ±30°) ─┘                                                 (intelligence.py:52-58)
                                    │
                                    ▼
              get_white_targets()  = 所有 RED 单位 intel.targets 并集
                                    + BLUE Ship 中 locker.locked 或 locker.frozen
                                    (engine.py:246-272)
                                    │
                                    ▼
              tzb_engine.get_state → white_observation = get_white_targets()[0]
                                    (tzb_engine.py:36-40, L99)
                                    │
                                    ▼
              pomdp_api._build_enemy_intel → /obs [敌方情报].active = name/position/velocity
                                    (main.py:646-694)
                                    ▼
              _build_legal_actions → [lock] = 存活 USV × active 敌舰
                                    (main.py:867-930)
```

要点:
- **任何一架白 UAV 探测到的目标, 全白方 (含所有 USV) 立即可见并可锁** —— 共享情报, 无需组网概念
  (虽然场景有 `StarNetwork4`, `sim:105`, 但 `get_white_targets` 本身就是全局并集, 网络非必需)。
- **被锁定或冻结的敌舰永远在白方情报里** (`engine.py:260-268`): 只要有任意白 USV 锁住了它,
  即使雷达失效它也会带着**真实坐标**持续出现在 `/obs`, 直到被击沉。
- 情报过期: 雷达航迹 2s (`radar.pyx:307-308`) + 情报黏性 **30s** (`intelligence.py:110-115`,
  `QB.radar_update_time=30`) → 目标脱离雷达约 **30s** 后从 `white_targets` 消失。
- `white_targets` 是 `set` → **同一目标按名去重**, 多个传感器重复探测不会产生重复条目。

### 3.2 Case A — 敌方 38km 处, 在 UAV 60km 内但超出 USV 35km 雷达

**结论: USV 可以锁定。** 实测 `probe_v5/P5`: `w1` 距 `b1` 39km (超过 35km USV 雷达),
`wuav1` 前出朝东飞 → `white_targets` 含 `b1` → `cmd_lock('w1','b1')=True`。
链: UAV 雷达 (60km) → intel → `get_white_targets` (engine.py:246) → USV 锁 (需 <40km)。

### 3.3 Case B — UAV 失去目标 (转向/出扇区/目标出60km)

- **已有锁: 继续。** 锁链跑在目标侧 locker, 与雷达无关 (`locker.py:92-147`)。
  实测 `probe_cap_sense2/P2`: UAV 转离后 +15s 双锁仍在推进, +300s 命中击杀。
- **新锁资格 (无既有锁时)**: 目标在 30s 黏性期内仍在 `white_targets` → 可新锁;
  **30s 后消失 → 无锁时新锁失败** (cmd_lock 要求 `unit2 in white_targets`, `engine.py:304`)。
- **目标已被他船锁住时**: 因 `engine.py:260-268` 永远在 `white_targets` → **可被任意其他 USV 再锁** (不限雷达)。

### 3.4 Case C — 多架 UAV / 多艘 USV 探测/锁定同一目标

- 身份去重: `white_targets` 是 set (engine.py:248,255), `/obs` 该目标只出现一次 (`main.py:652-658`)。
- 多 USV 同锁一目标: 合法, 各自独立链 (`locker.locked_info` 按攻击者名分键);
  击杀条件是**所有链累计命中 ≥2** (`locker.py:112-113`)。实测 P2 双链 300s 内击杀。
- 无"抢锁互斥": 只有**同一艘 USV** 被限制为一锁一目标且不可切换 (`engine.py:318`)。

---

## 4. Agent 可见的己方状态 (Friendly State Available to the Agent)

### 4.1 `/status` 资源快照 (结构化, 建议主数据源) — `main.py:1557-1655`

`white_usv_states` 白名单 (main.py:1605-1622), 每艘 USV:
`name / is_alive / position / velocity / course / speed / is_locked / is_locking / is_frozen /
 locked_attacker / relative_orientation / locking_unit / locked_times / uav`(机库UAV名)

`white_uav_states` 白名单 (main.py:1624-1629), 每架 UAV:
`name / is_alive / position / velocity / course / speed / battery / battery_format /
 is_charging / is_at_usv / home_name`

`white_observation` (main.py:1630-1644):
- `active` ([雷达捕获]): 探测到的敌舰 **name/position/velocity 真值**;
- `passive` ([被动告警]): 仅 name/bearing/detected_by (被谁锁到的方位告警, `_build_enemy_intel` main.py:646-694)。
  被动告警**没有坐标** → 只能用于判威胁方位。

另有 `奖励信号` (env_score_flat, tzb_engine.py:138-147)、`局内时间`、`等待指令`、`行动历史`。

### 4.2 `/obs` (main.py:701-860) 与 `/legal_actions` (main.py:867-964)

- `/obs`: 文本分节 `[Info]/[我方无人艇]/[我方无人机]/[敌方情报]/[派生信号]`, 含存活统计。
  敌情 active 条目 = 雷达捕获 (可执行锁定); passive 条目 = 被动告警 (仅方位)。
- `/legal_actions`: 5 组 `[move]/[lock]/[launch_uav]/[fly]/[land_uav]` + notes
  ("当前已锁定, 再次发送无效"、"[fly] 和 [land_uav] 互斥" 等)。

### 4.3 合法 vs 黑方泄漏

| 项 | 状态 | 说明 |
|---|---|---|
| 己方全部状态 | **合法真值** | `/status` 白名单仅白方字段 (`main.py:1605-1629`) |
| 敌方真值 (位置/速度) | **只来自探测** | `white_observation` = `get_white_targets` (engine.py:246) |
| 敌方 USV 状态 | **API 不透出** | `black_usv_states` 仅 `name/is_alive/is_frozen/locked_times` (**无坐标**, tzb_engine.py:96-104), 且 API 不转发任何 black_* |
| 敌方 UAV 状态 | **API 不透出** | `black_uav_states` 含动力学但被 API 丢弃 |
| L4 身份泄漏 | 轻微 | 被动告警带攻击者**名字** (`_build_enemy_intel`, main.py:669-681) |
| L5 幽灵被锁 | **Agent 端 bug 源** | `locked_attacker` 只增不删 (`locker.py:66-90` `emy_name` 永不删除); **判断真实被锁应以 `is_locked`/`locked` 布尔为准**, 不要信任列表长度 |

> **公平性结论**: 走 HTTP API 的 Agent 只能拿到公平观测; 敌方位置永远是"探测真值 + 30s 过期",
> 没有黑方坐标硬编码可依赖。`BLACK_Y` 式场景先验 (旧 agent_defense/attack/win) 属作弊且对 15+15 失效。

---

## 5. 命令语义 (Command Semantics)

统一: 动作经 `/apply` 发送, 校验于 `_ACTION_SCHEMAS` (main.py:543-582) 与
`_parse_action_text` (main.py:989-1043), 执行于 `_execute_one_action` (main.py:1050-1190)。
引擎执行后 `release_until_time = current_time + 30` (MACRO_STEP, main.py:81), 即**每 30 仿真秒一批**。

### 5.1 `move` — USV 机动

| 字段 | 内容 |
|---|---|
| 格式 | `white_usv1 移动 target_speed=<0-100> target_course=<0-360>` |
| 参数 | `target_speed` [0,100] (引擎钳制到 20), `target_course` [0,360] (北0顺时针) |
| 适用平台 | 存活白 USV |
| 前置条件 | RED ShipMotorTZB; speed≥0; course∈[0,360] (`tzb_engine.py:151-169`) |
| 持续性 | **持久** — 巡航至新指令 |
| 状态变化 | `motor.set_target_speed/angle`; 加速 2 m/s²; 转向瞬时 |
| 时长 | 每宏步生效, 跨步持续 |
| 失败条件 | 负速/越界航向被拒; 单位已死被跳过 |
| 示例 | `white_usv1 移动 target_speed=20 target_course=90` |

### 5.2 `lock` — USV 锁定敌舰

| 字段 | 内容 |
|---|---|
| 格式 | `white_usv1 锁定 <敌USV名>` |
| 参数 | `target` 必须在 `[lock]` 合法列表 (active 敌舰) |
| 适用平台 | 存活白 USV (Ship) |
| 前置条件 | 目标在 `white_targets` 且 <40km; 本船未锁他船 (`engine.py:285-320`) |
| 持续性 | **一次性 + 目标侧自主计时**; 重复发送被跳过 (`main.py:1085-1093` 若已锁该目标 → `skipped=True`) |
| 状态变化 | 目标侧 `locked_info[attacker]` 建立; 300s 后 80% 命中 → 冻结 300s; 累计2次命中击沉 (`locker.py:92-147`) |
| 时长 | 300s/次; 2次/击杀; 锁断条件: 攻击者>40km 或 目标沉没 |
| 失败条件 | 目标不可见/距离超限/一船一锁冲突/阵营错误 |
| 示例 | `white_usv3 锁定 black_usv5` |

### 5.3 `launch_uav` — UAV 起飞

| 字段 | 内容 |
|---|---|
| 格式 | `white_uav1 从 white_usv1 起飞 target_speed=<0-100> target_course=<0-360>` |
| 参数 | `home` 母船名; speed/course 起飞后巡航 |
| 适用平台 | 机库内 UAV + 存活母船 |
| 前置条件 | UAV ∈ `home.planes` (`platform.py:213-232`) |
| 持续性 | 一次性; 起飞后持续飞行直至新指令 |
| 状态变化 | 雷达开、`is_at_home=False`、`motor.remove_home`、`take_off_time=now`、电池开始消耗 |
| 时长 | 直到降落/耗尽 |
| 失败条件 | UAV 不在机库 → 不在 `[launch_uav]` 列表 |
| 示例 | `white_uav2 从 white_usv2 起飞 target_speed=150 target_course=90` |

### 5.4 `fly` — UAV 空中机动

| 字段 | 内容 |
|---|---|
| 格式 | `white_uav1 飞行 target_speed=<0-100> target_course=<0-360>` |
| 参数 | 同 `move` (schema 上限 100; 引擎允许到 150) |
| 适用平台 | 空中存活 UAV (`is_at_usv=False`) |
| 前置条件 | 同 `send_command` (RED MotorTZB) |
| 持续性 | **持久** |
| 状态变化 | 目标 speed/course; 加速 10 m/s²; 航向即雷达扇区指向 |
| 时长 | 每宏步生效, 跨步持续 |
| 失败条件 | 与 `move` 相同 |
| 示例 | `white_uav1 飞行 target_speed=100 target_course=45` |

### 5.5 `land_uav` — UAV 降落

| 字段 | 内容 |
|---|---|
| 格式 | `white_uav1 降落到 white_usv3` |
| 参数 | `target` 任意存活白 USV |
| 适用平台 | 空中 UAV × 存活 USV |
| 前置条件 | 同阵营; `dist<10000` 且 UAV `speed<100` (`engine.py:363-374`) |
| 持续性 | 一次性; 降落即转机库态 |
| 状态变化 | 目标 USV 机库接收、雷达关、`is_at_home=True`、电池开始充电 (`platform.py:234-246`) |
| 时长 | 立即 (或经 API 引导 ~speed=50 抵近后) |
| 失败条件 | 距离>10km 时 API 先引导 (`main.py:1149-1170`); 若 USV 已有机库/死亡则失败 |
| 示例 | `white_uav1 降落到 white_usv3` (跨母船合法) |

---

## 6. 最终能力矩阵 + AGENT DESIGN IMPLICATIONS

### 能力矩阵

| 能力 | USV (白) | UAV (白) | 黑方对应 |
|---|---|---|---|
| 最大速度 | **20 m/s** | **150 m/s** | USV 10 m/s (sim:124-129); UAV 30 m/s 巡航 (sim:146, 航路点覆盖为30) |
| 加速度 | 2 m/s² | 10 m/s² | 同型 (对称) |
| 转向 | 瞬时 | 瞬时 | 同型 |
| 指令 | move / lock / launch_uav / land_uav | fly / land_uav | 敌固定策略 (sim:167-176 每秒锁可见白USV) |
| 雷达 | 35km 全向 | 60km ±30° 前向 | 30km 全向 / 60km ±30° (sim:109-110,132-134) |
| 雷达周期 | 2s | 2s | 2s |
| 探测 | fixed 确定性 | fixed 确定性 | 同 |
| 锁定 | <40km, 一船一锁, 300s/80%/冻结/2次击杀 | ✗ 无 locker | 镜像 (black_cmd_lock engine.py:321) |
| 生存 | 被锁→冻结(停船+雷达关) | 仅电池/母船沉没致死 | 被锁→冻结 |
| 电池 | ✗ | 25000s 线性, <0 即死, 机库充电 1.39/s | 同 (sim:159-161) |
| 搭载 | 1 UAV/船 | 受母船约束 | — |
| 情报贡献 | 35km 全向建航 | 60km 前向建航 | 黑方全局情报同理 (get_black_targets engine.py:274-283) |

### === AGENT DESIGN IMPLICATIONS ===

**USV 职责 (Agent 需要做的)**
1. **保持 <40km 锁定距离**: 锁建立后 300s 计时全在目标侧, 但一超出 40km 锁即断 (locker.py:97)。
   白 USV 20 m/s、黑 10 m/s, 相对闭合 30 m/s → 追击中锁断风险低, 但撤退/绕行必须防断。
2. **一船一锁、绝不切换**: 锁上就锁到底, 换目标 = 重建并重计 300s (engine.py:318)。
3. **多船协同收割**: 2 艘 USV 同锁 1 目标 = 双掷, 300s 击杀 (实测 P2); 避免 3+ 艘抢同一目标 (锁调度)。

**UAV 职责**
1. **前出 60km 扇形侦察并回传**: 任何 UAV 探测 → 全白方可锁 (engine.py:246)。这是 USV 超 35km 锁定的唯一途径。
2. **管好电量**: 25000s 线性消耗、<0 即死、无自动返航 (uavbattery.py:70-72)。必须"低频巡检 + 定时返航回充"。
3. **航向即扇区**: 悬停雷达楔形冻结; 扫描靠飞 (+ 需知道 30s 情报黏性留给返回的窗口)。

**编队级协调**
1. **先侦察后接敌**: 开战即前出若干 UAV 东扫, 让 USV 在 35km 外就能锁定 (Case A)。
2. **锁定目标永久可见**: 一旦锁上, 该目标坐标持续在 `/obs` → 可安全交给其他 USV 续锁/换防, 不依赖雷达。
3. **情报有 30s 过期**: 雷达丢失目标后仍有 30s 决策窗 (外推/换锁/继续追); 别在过期后才发锁 (会失败)。

**NOT 由 LLM 控制的**
1. **锁定 300s 计时与命中**: 引擎目标侧自主 (locker.py:92-147)。Agent 只需"锁上 + 维持距离", 不要重发。
2. **冻结的 300s 自动解冻**: 冻结船停船+雷达关, 300s 自动恢复 (locker.py:128-145), Agent 无需干预。
3. **飞行/巡航的物理运动**: 位置、速度、航向由引擎每 0.1s 推进; Agent 只下目标级指令。
4. **击杀的最终判据**: 累计 2 次命中击沉 (含机载 UAV 连带), 由引擎判定 (locker.py:112-118)。

**剩余不确定性 (供实现期快速核验, 不阻塞设计)**
1. **编译 .so 与 .pyx 的差异**: 转向实测"瞬时"但源码算得 4 tick (0.4s) —— 精确转向耗时以实测为准,
   对 30s 宏步调度无影响; 若要精确短距走位, 建议再探针验证 (已留 `probe_cap_turn9` 可复跑)。
2. **数据源 pkl 缓存**: 引擎运行时 DB 来自 `cache_json.pkl` (base_engine.pyx:482 默认 cache=True),
   与磁盘 json 不一致 (max_speed 20 vs 10, radar_update_time 30 vs 5)。若运维侧重建缓存, 数值会变
   → 正式比赛前应在真实启动的 sim_server 上确认一次。
3. **被动告警的 relative_orientation 是否伴随每条链刷新**: L5 "幽灵被锁" 说明 locked_attacker
   会残留旧攻击者; 精确的方位刷新节奏未逐一实测, Agent 端以 `is_locked` 布尔为准即安全。
4. **冻结后重新锁定**: 冻结船仍在 `white_targets` (engine.py:260-268) → 可被新锁;
   但解冻后旧链需在 40km 内重建 —— 具体到"冻结中被他船锁定是否计命"未做专项探针 (从代码看按正常链计时)。

---

### 附录: 本轮回证据 (probe_rules/, 全部短时、未改 simulator)

| 探针 | 结论 |
|---|---|
| `probe_cap_speed.py` | 白 USV 10→20 加速, 30s 位移 576m ⇒ 有效 max_speed=20, max_acce=2 |
| `probe_cap_turn8/9.py` | 90°/180° 转向 ≈瞬时 (≤0.15s), 巡航持久 |
| `probe_cap_sense.py` | 白观测 30s+ 黏性 (锁驱动); 电池线性; land 非母船受 speed≥100 限制 |
| `probe_cap_sense2.py` | P1 纯情报黏性 ~25-35s; P2 双锁同目标 +300s 击杀 + 锁后可见; P3 电池<0 即 kill |
| `probe_cap_sense3.py` | intel model=`QB`, radar_update_time=30; acquire 直测 |
| `probe_cap_land.py` | 跨母船降落成功 (距8.9km, speed50); 再起飞复用 |
| `probe_intel_src.py` | intelligence 组件 model=`QB`; DB 值确认 |

### 关键文件索引

- `pomdp_api/main.py` — `_ACTION_SCHEMAS` L543; `_build_enemy_intel` L646; `_build_obs_text` L701;
  `_build_legal_actions` L867; `_execute_one_action` L1050 (land 引导 L1149); `/status` 白名单 L1605-1629
- `simulation/core/tzb_engine.py` — `get_state` L20-149 (black_usv_states L96-104 无坐标; 结束条件 L120-135);
  `send_command` L151-169
- `simulation/core/engine.py` — `get_white_targets` L246-272; `cmd_lock` L285-320; `cmd_uav_takeoff` L352;
  `cmd_uav_land` L363-374; `put_uav_in_ship` L376-392
- `simulation/arsenal/locker.py` — `is_locked` L66-90; `_locked_work` L92-147 (300s/80%/冻结/击杀/机载UAV);
  `_locking_work` L149-162
- `simulation/arsenal/tzb_motor.py` — `set_target_speed` L40; `_move` L62-134 (转向 L84-93; 加速 L99-103)
- `simulation/arsenal/platform.py` — `heading` L82-87; `load_uav` L89-94; `take_off` L213-232; `land` L234-246
- `simulation/arsenal/uavbattery.py` — `__init__` L13-32; `_battery_work` L67-79 (<0→kill); `charge` L58-64
- `simulation/arsenal/radar.pyx` — `acquire` L83-131; `_search` L260-268; `_detect` L270-313 (轨迹 2s 保留 L307-308)
- `simulation/arsenal/intelligence.py` — `targets` L52-54; `_work` L110-115 (30s 过期)
- `sim_script/20250819TZB/sim_20250819测试用例1.py` — 15+15 场景; 雷达覆盖 L71-73/87-89/109-111/132-134;
  black_strategy L167-176
- `simulation/database/json/*.json` + `cache_json.pkl` — 运行时 DB 实际来源 (base_engine.pyx:482)
