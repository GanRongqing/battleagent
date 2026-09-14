# Harness × Behavior Tree — 接口参考文档

> 版本：与当前 `bt_harness_interface.py` / `bt_real_trees.py` 一致（2026-08）
> 目的：完整记录 Harness ↔ Real Behavior Tree 之间的接口契约、数据结构、生命周期语义、
> 决策权边界、动作映射与两种运行模式。任何接入方应以本文档为准。
> 相关冻结配置见 `bt_regression_eval/config_manifest.json`。

---

## 0. 架构总览

```
Harness（frozen）
  Observation → Track/Belief → Marginal Allocator
        │  (决定 WHO + WHAT：platform / target / task_type / role / constraints)
        ▼
  TaskCommand  ───────────────►  BTPlatformExecutive.submit_task(command) → TaskAck
        │                                │
        │  tick(ExecutionContext)        │  (每次决策步)
        ▼                                ▼
  ExecutionContext（合法 runtime 快照）   Real USV/UAV BehaviorTree
        ─────────────────────────────────► bt_bridge.pre_tick(ExecutionContext→Blackboard)
                                           tree.tick() → (status, ActionRequest[], TaskFeedback)
                                           bt_bridge.post_tick(Blackboard→BTStepResult)
        ▼
  ActionRequest[]（意图级）
        ▼
  BTActionAdapter（ActionRequest → action_text / action_type）
        ▼
  ActionSafety（合法校验）→ POST /apply → simulator
        ▼
  /apply 结果 → 下一 tick 的 ExecutionContext.safety_feedback / controller_feedback
  TaskFeedback（status / phase / target / need_reallocation / reason_code）→ Harness
```

**决策权边界（HARNESS_BT_MODE）**
- Harness 拥有 **WHO + WHAT**：platform、target、task_type、role、major constraints。
- Behavior Tree 拥有 **HOW / NEXT PHASE**：approach / orbit / track / engage / search / return / dock / hold / reacquire。
- BT **内部不允许自行重新决定“锁谁”**：`target_id` 一旦由 TaskCommand 指派即不可变；
  目标丢失 → 局部 reacquire（同 target）；超时 → `need_reallocation=True` 交回 Harness。

---

## 1. PlatformExecutive 契约（对外接口，禁止改动）

```python
class PlatformExecutive(abc.ABC):
    def submit_task(self, command: TaskCommand) -> TaskAck: ...
    def cancel_task(self, request: CancelTaskRequest) -> TaskAck: ...
    def tick(self, context: ExecutionContext) -> BTStepResult: ...
```

实现：`BTPlatformExecutive`（每个平台一个实例，包装一颗真实行为树）。

| 方法 | 语义 | 返回 |
|---|---|---|
| `submit_task(command, now_sim=None)` | 校验并登记任务（可带当前仿真秒做 expired 判定）；把任务写入 blackboard / tree.active_task；**不执行 tick** | `TaskAck` |
| `cancel_task(request)` | 取消 active task，重置与该 task 相关的 memory 分支，**不销毁整棵树** | `TaskAck` |
| `tick(context)` | 严格包装 `bt_bridge.pre_tick → tree.tick → bt_bridge.post_tick`，构造 `BTStepResult` | `BTStepResult` |

---

## 2. 数据结构全字段

### 2.1 TaskCommand（Harness → BT 的任务指派）

| 字段 | 类型 | 默认 | 含义 |
|---|---|---|---|
| `task_id` | `str` | — | 任务唯一标识（建议 `platform_target_tasktype`） |
| `platform_id` | `str` | — | 平台名，如 `white_usv1` |
| `platform_type` | `PlatformType` | — | `USV` / `UAV` |
| `task_type` | `TaskType` | — | 任务族（见 §3） |
| `target_id` | `Optional[str]` | `None` | 被指派目标（**不可变**，如 `enemy_3` / `black_usv9`） |
| `role` | `str` | `"default"` | 角色标签 |
| `revision` | `int` | `1` | 同一 task 的版本号（同 task 更高 revision = 更新） |
| `priority` | `int` | `0` | 优先级（高优先可抢占普通任务） |
| `plan_id` | `str` | `""` | 计划标识（用于 plan 级版本管理） |
| `plan_revision` | `int` | `1` | 计划版本号（同 plan 更低 revision = 过期） |
| `valid_from` | `Optional[float]` | `None` | 生效起始仿真秒（在此之前**不得执行**） |
| `valid_until` | `Optional[float]` | `None` | 失效仿真秒（之后任务 expired，无动作） |
| `preemptible` | `bool` | `True` | 是否允许被普通任务抢占（`False` 时仅 safety override 可抢占） |
| `safety_override` | `bool` | `False` | 安全任务标志；可抢占任何任务（含非可抢占） |
| `allow_local_reacquire` | `bool` | `True` | 目标丢失时是否允许 BT 局部 reacquire |
| `max_search_time` | `float` | `60.0` | 局部 reacquire 窗口（超时 → need_reallocation） |
| `constraints` | `Dict` | `{}` | 主要约束（如 UAV `waypoint`/`base`） |

### 2.2 TaskAck（submit/cancel 的应答）

| 字段 | 类型 | 含义 |
|---|---|---|
| `code` | `AckCode` | 结果码（见 §3） |
| `task_id` | `str` | 对应任务 |
| `platform_id` | `str` | 对应平台 |
| `message` | `str` | 说明 |
| `timestamp` | `float` | wall 时间戳 |

### 2.3 CancelTaskRequest

| 字段 | 类型 | 含义 |
|---|---|---|
| `platform_id` | `str` | 平台 |
| `task_id` | `str` | 要取消的任务 |
| `reason` | `str` | 取消原因（默认 `"cancel"`） |

### 2.4 ExecutionContext（Harness → BT，每 tick）

| 字段 | 类型 | 含义 |
|---|---|---|
| `platform_id` | `str` | 平台名 |
| `platform_type` | `PlatformType` | 平台类型 |
| `sim_time` | `float` | 当前仿真秒 |
| `platform_state` | `Dict` | 自身状态：`position/speed/heading/is_alive`；USV 另含 `is_locking/locking_unit`；UAV 另含 `is_at_usv`（是否在舰上） |
| `tracks` | `Dict` | 信念航迹 `{name: {position, visible, confidence, is_ship}}`（仅合法观测） |
| `controller_feedback` | `Optional[Dict]` | 上一个控制器结果 |
| `safety_feedback` | `Optional[Dict]` | `{action_text: PASS/CLAMPED/MODIFIED/REJECTED/OVERRIDDEN}`，来自上次 /apply |
| `nearby_friendlies` | `List[Dict]` | 邻近友方（可选） |
| `hazards` | `List[Dict]` | 危险物（可选） |

**合法约束**：`ExecutionContext` 不得含 `ground_truth / true_enemy_state / future_trajectory / hidden_enemy / undetected_target_state`。`bt_bridge.pre_tick` 负责把 ExecutionContext 写入 Blackboard。

### 2.5 ActionRequest（BT → Harness，意图级）

| 字段 | 类型 | 含义 |
|---|---|---|
| `platform_id` | `str` | 平台 |
| `action_kind` | `ActionKind` | 意图（见 §3） |
| `target_id` | `Optional[str]` | 目标（必须与指派一致） |
| `waypoint` | `Optional[(float,float)]` | 航点 |
| `course` | `Optional[float]` | 航向（度） |
| `speed` | `Optional[float]` | 速度 |
| `meta` | `Dict` | 附加（如 UAV `home`） |
| `.channel`（属性） | `ActionChannel` | 由 `ACTION_CHANNEL` 推导（同平台同 tick 每 channel ≤1 个请求） |

### 2.6 TaskFeedback（BT → Harness，每 tick）

| 字段 | 类型 | 含义 |
|---|---|---|
| `platform_id` | `str` | 平台 |
| `task_id` | `str` | 当前任务 |
| `status` | `TaskStatus` | `PENDING/ACCEPTED/RUNNING/COMPLETED/REJECTED/CANCELLED` |
| `phase` | `Phase` | 当前执行阶段 |
| `target_id` | `Optional[str]` | 当前目标 |
| `target_visible` | `bool` | 目标是否可见 |
| `target_confidence` | `float` | 目标信念置信 |
| `need_reallocation` | `bool` | 是否请求 Harness 重新分配 |
| `reason_code` | `FeedbackReason` | 反馈原因（见 §3） |

### 2.7 BTStepResult（tick 的返回）

| 字段 | 类型 | 含义 |
|---|---|---|
| `tick_id` | `int` | 单调 tick 计数 |
| `platform_id` | `str` | 平台 |
| `root_status` | `str` | `RUNNING / SUCCESS / FAILURE / IDLE` |
| `action_requests` | `List[ActionRequest]` | 本 tick 意图动作 |
| `task_feedback` | `TaskFeedback` | 本 tick 反馈 |
| `active_branch` | `str` | 当前活动分支（phase） |

---

## 3. 枚举全表

### PlatformType
`USV` 水面无人艇 ｜ `UAV` 无人机

### TaskType（任务族）
| 值 | 适用 | 语义 |
|---|---|---|
| `INTERCEPT_LOCK` | USV | 拦截并锁定指派目标 |
| `ENGAGE_TARGET` | USV | 交战/攻击指派目标 |
| `HOLD_POSITION` | 两者 | 待命/巡逻（未指派时保持移动） |
| `COOPERATIVE_LOCK` | UAV | 协同锁定（传感器 standoff 环绕） |
| `SITUATION_UPDATE` | UAV | 态势更新（飞往航点搜索） |
| `RETURN_RECHARGE` | UAV | 返航充电 |

### TaskStatus
`PENDING`（尚未执行）→ `ACCEPTED`（已登记）→ `RUNNING`（执行中）→ `COMPLETED` / `REJECTED` / `CANCELLED`

### AckCode（submit/cancel 结果）
| 值 | 含义 |
|---|---|
| `ACCEPTED` | 新任务接受 |
| `ACCEPTED_WITH_PREEMPTION` | 接受新任务并抢占旧任务 |
| `DUPLICATE_IGNORED` | 同 task_id + 同 revision 重复提交，忽略（不重初始化） |
| `STALE_REJECTED` | 更低 task/plan revision，拒绝 |
| `EXPIRED` | valid_until 已过 |
| `INVALID_PLATFORM` / `INVALID_TYPE` | 平台名/类型不匹配 |
| `BUSY` | 当前任务不可抢占且非 safety override |
| `CANCELLED` / `NOT_FOUND` | 取消成功 / 未找到匹配任务 |

### ActionKind（BT 意图）
`NAVIGATE_TO` 飞往/驶往航点 ｜ `APPROACH_TARGET` 接近目标 ｜ `ORBIT_TARGET` 环绕 ｜
`TRACK_TARGET` 跟踪 ｜ `ENGAGE_TARGET` 锁定交战 ｜ `RETURN_TO_BASE` 返航 ｜
`LAND_OR_DOCK` 降落/停靠 ｜ `HOLD` 待命 ｜ `REACQUIRE` 重搜 ｜ `LAUNCH` 起飞

### ActionChannel（同平台同 tick 冲突约束） 
`NAVIGATION`（航路类）｜ `SENSOR`（感知类）｜ `WEAPON`（武器类）｜ `SYSTEM`
映射见下：

| ActionKind | Channel |
|---|---|
| NAVIGATE_TO / APPROACH_TARGET / ORBIT_TARGET / TRACK_TARGET / RETURN_TO_BASE / LAND_OR_DOCK / HOLD / LAUNCH | **NAVIGATION** |
| REACQUIRE | **SENSOR** |
| ENGAGE_TARGET | **WEAPON** |

规则：同平台同 tick **每个 channel 至多 1 个 ActionRequest**（允许 NAVIGATION+WEAPON、NAVIGATION+SENSOR，禁止两个 NAVIGATION）。

### FeedbackReason
`none` ｜ `target_lost` 目标丢失（reacquire 中）｜ `target_lost_timeout` 重搜超时 ｜
`need_reallocation` 需要重分配 ｜ `task_completed` 完成 ｜ `safety_rejected` 动作被拒 ｜
`safety_override` 安全接管 ｜ `unreachable` 不可达 ｜ `expired` 过期 ｜
`not_yet_valid` 未到生效时间 ｜ `blocked` 被阻止（禁 reacquire）｜ `preempted` 被抢占

### Phase
`approach / orbit / track / engage / search / return / dock / hold / reacquire`

---

## 4. submit_task 生命周期语义（判定顺序）

```
1. platform_id / platform_type 不匹配         → INVALID_PLATFORM / INVALID_TYPE
2. now_sim > valid_until                      → EXPIRED
3. 同 plan_id 且 plan_revision 更低           → STALE_REJECTED
4. 同 task_id：
     revision 相同                            → DUPLICATE_IGNORED（不重初始化、不清 phase）
     revision 更低                            → STALE_REJECTED
     revision 更高                            → 接受为更新（ACCEPTED）
5. 不同 task_id（抢占）：
     允许 = safety_override 或 旧任务 preemptible 或 新 priority > 旧
     不允许                                 → BUSY
     允许                                    → ACCEPTED_WITH_PREEMPTION（旧任务反馈 PREEMPTED /
                                               SAFETY_OVERRIDE）
6. 接受后：写 blackboard / tree.active_task；重置 lost_since/reacquire/phase；
   root.reset() 清 memory 分支（仅在新任务/更新时）
```

**任务持久化**：只要 `task_type/target/role/主要约束` 未变，**不要每 tick 重发 submit**；
只需反复 `tick()`。只有 target 变化 / 任务变化 / 显式重分配 / revision 更新 / 抢占才重新 submit。

**valid_from / valid_until（tick 时）**：`sim_time < valid_from` → 不执行（NOT_YET_VALID，无动作）；
`sim_time > valid_until` → EXPIRED（无动作，need_reallocation=True）。

---

## 5. tick 语义（真实树，memory=True）

```
无 active_task           → IDLE（无动作）
valid_from/valid_until 校验 → 见上
root（Selector 非 memory，保证每 tick 重查 safety guard）
  ├─ safety_hold：safety_feedback 含 REJECTED/OVERRIDDEN → HOLD + reason
  ├─ USV：visible → Sequence(approach → engage)   # approach RUNNING(接近)/SUCCESS(进锁距)
  │              lost  → reacquire（memory，allow_local_reacquire；超时 need_reallocation）
  │              无目标 → hold_fallback
  ├─ UAV：cooperative_lock → Sequence(approach → orbit)
  │       situation_update → navigate（docked 时先 LAUNCH）
  │       return_recharge → Sequence(return → dock)
  └─ hold_fallback
```

- **USV**：远离→`approach`(APPROACH_TARGET)；进入锁距→先发一次 `ENGAGE_TARGET`(lock) 再 `ORBIT_TARGET`(standoff move)；
  已锁定（platform_state.is_locking）→ 不再重复 lock，只发 standoff（保护 300s 锁链）。
- **UAV**：在舰上（is_at_usv）→ 先 `LAUNCH`（launch_uav），起飞后再飞。
- **Safety**：REJECTED/OVERRIDDEN → 下 tick 不再重复被拒 primitive，改 HOLD/fallback；
  CLAMPED/MODIFIED → 不误判失败，继续可行分支。
- **Target 不可变**：所有 target 引用来自 blackboard.target_id（TaskCommand）；树内无 allocator，
  环境里 enemy_4 更近 / enemy_5 置信更高 / enemy_6 进入武器射程 都**不会**改 target。

---

## 6. BTActionAdapter（ActionRequest → /apply payload）

| ActionKind | action_text | action_type |
|---|---|---|
| `LAUNCH` | `white_uav1 从 white_usv1 起飞 target_speed=100.0 target_course=90.0` | `launch_uav` |
| `NAVIGATE_TO / APPROACH / ORBIT / TRACK / REACQUIRE` | `white_usv1 移动 target_speed=20.0 target_course=92.6`（UAV 用 `飞行`） | `move` / `fly` |
| `ENGAGE_TARGET` | `white_usv1 锁定 black_usv9` | `lock` |
| `RETURN_TO_BASE` | `white_uav1 飞行 target_speed=100.0 target_course=270.0` | `fly` |
| `LAND_OR_DOCK` | `white_uav1 降落 white_usv1` | `land_uav` |
| `HOLD` | `white_usv1 移动 target_speed=20.0 target_course=90.0` | `move` |

`/legal_actions` **不变**：继续返回完整合法动作空间；BT 输出只是其中一个决策来源，经
`ActionSafety.filter` 校验后 `POST /apply`。

---

## 7. 两种运行模式

| | STANDALONE_BT_MODE | HARNESS_BT_MODE（当前） |
|---|---|---|
| 驱动 | bt_agent 自己 get_state → tick →（原 gRPC apply） | Harness allocator → submit_task → tick(context) → ActionRequest |
| simulator 写入 | （原 BT 直连 gRPC） | **只有 Harness 一个 writer：POST /apply** |
| BT gRPC 写入 | 允许（原行为） | **= 0**（bt_bridge 网络职责为 0：pre_tick 只填 blackboard，post_tick 只打包） |

HARNESS 模式下 BT 侧任何 `requests/grpc/engine.apply/get_state` 直写都被 poison-patch 禁止。

---

## 8. 文件清单

| 文件 | 内容 |
|---|---|
| `bt_harness_interface.py` | 接口层：枚举、数据结构、`PlatformExecutive`、`BTPlatformExecutive`、`BTActionAdapter`（含 `StubBehaviorTree/StubBTBridge` 仅供接口单测，不进生产路径） |
| `bt_real_trees.py` | 真实 BT：框架（Status/Node/Selector/Sequence/Behavior/BehaviorTree, memory）+ `build_usv_tree` / `build_uav_tree` + `BTBridge` + `make_executive_tree` |
| `test_bt_harness_interface.py` | 8 项接口单测（53 checks） |
| `test_bt_real_trees.py` | 真实树验证 TEST A–E + standalone（60 checks） |
| `test_bt_wide.py` | 广覆盖 contract 测试（83 checks：lifecycle/revision/cancel/preempt/persist/target/reacquire/三态/channel/safety 矩阵/platform lifecycle/no-ground-truth） |
| `bt_harness_e2e.py` | 真实 simulator E2E（→ `REAL_BT_HARNESS_TRACE.md`） |
| `bt_integration_run.py` / `bt_regression_run.py` / `bt_finalize.py` | 18 局集成 + 30+30 配对回归 + 报告/图（`bt_regression_eval/`） |

---

## 9. 端到端示例（简化）

```python
ex = BTPlatformExecutive("white_usv1", PlatformType.USV)          # 真实 USV 树
ack = ex.submit_task(TaskCommand(
    task_id="white_usv1_black_usv9_intercept",
    platform_id="white_usv1", platform_type=PlatformType.USV,
    task_type=TaskType.INTERCEPT_LOCK, target_id="black_usv9"))
# 每步：
res = ex.tick(ExecutionContext(
    platform_id="white_usv1", platform_type=PlatformType.USV, sim_time=now,
    platform_state={"position":[...], "is_locking":False, ...},
    tracks={"black_usv9":{"position":[...],"visible":True,"confidence":1.0}},
    safety_feedback=last_apply_feedback))
payload = BTActionAdapter().to_apply_payload(res.action_requests)  # {"actions":[...]}
safe = ActionSafety().filter([(a["action_text"],a["action_type"]) for a in payload["actions"]], obs, legal)
apply_resp = http("/apply", json=payload)
last_apply_feedback = {item["动作"]: ("REJECTED" if item["跳过"] else "ACCEPTED")
                       for item in apply_resp["执行结果"]}
fb = res.task_feedback  # phase / target / need_reallocation / reason_code → Harness
```

---

## 10. 当前验证状态

- 单元/契约测试：196 checks 全 PASS（submit lifecycle / revision / cancel / preempt /
  persist / target immutable / reacquire / memory / channel / safety 矩阵 / platform lifecycle / no-ground-truth）。
- 18 局集成（3 规模 × B0/B3 × 3 seeds）：接口 8 项 gate 全 0（engine/API/invalid/ownership/channel/
  BT-write/orphan-feedback/orphan-action），96k+ 动作全部 PASS，0 被拒。
- 30 对配对回归：target 协议一致率 1.0，task-family 一致率 1.0，unexplained divergence = 0。
  胜率差距（legacy 30/30 vs BT 0/30）为**预期策略差异**：最小真实树缺少 legacy 控制器的
  standoff-band / coverage 管理，USV 近战损耗高——属策略差距，非接口回归；按约束未对树做胜负 tuning。
