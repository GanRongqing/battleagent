# 仿真 POMDP API 使用说明（API 端口）

仿真的对外 HTTP 决策接口。内部经 gRPC 连仿真后端（base_server），
外部供决策客户端使用。

## 端口与进程

```
决策方 ──HTTP──▶ POMDP API (本目录, :8000)
                 └──gRPC──▶ 仿真后端 base_server (:6000)
                             └─ 仿真引擎进程 ×5 (:6001-6005)
```

| 进程 | 启动命令 | 端口 |
|---|---|---|
| 仿真后端 | `cd hsystem/simserver && python base_server.py` | gRPC 6000（引擎 6001-6005） |
| POMDP API | `cd pomdp_api && python app.py`（或仓库根目录 `python -m pomdp_api.app`，两者均可） | HTTP 8000 |
| 决策方 | 任意 HTTP 客户端 | 无（仅出站） |

## 启动

**前提**：每个终端先激活仿真环境（仿真包基于 Python 3.8 构建，
base 环境的 3.14 无法运行）：

```bash
conda activate hsystem_env
```

**完整启动（三个终端，按顺序）：**

```bash
# 终端 1 — 仿真后端
export PYTHONPATH="/home/xuandu/Projects/hsystem/hsystem:${PYTHONPATH}"
cd hsystem/simserver
python base_server.py

# 终端 2 — POMDP API（后端在本机时设 SIM_HOST=127.0.0.1；默认 192.168.252.41）
export PYTHONPATH="/home/xuandu/Projects/hsystem/hsystem:${PYTHONPATH}"
cd pomdp_api
SIM_HOST=127.0.0.1 python app.py

# 终端 3 — 决策方：经 HTTP 调 /apply 执行动作
```

**后端和 API 已在跑时**：决策方直接经 HTTP 调用即可。若启动时对局已存在
（/start 返回 409），POST /reset 重开新局。

**停止**：先停决策方 → 停 API → 停后端。

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `SIM_HOST` | `192.168.252.41` | 仿真后端 IP（本机运行时设 127.0.0.1） |
| `SIM_PORT` | `6000` | 后端 gRPC 端口 |
| `APP_PORT` | `8000` | 本 API 监听端口 |
| `MACRO_STEP` | `30` | 宏观步步长（仿真秒，每次 /apply 推进） |
| `API_URL` | `http://127.0.0.1:8000` | 客户端连接地址（client.py / bt_agent 用） |
| `SCRIPT` | `测试用例1` | 仿真脚本名（bt_agent 用） |
| `STEP_DELAY` | `0.5` | 决策步间隔秒（bt_agent 用） |

## 端点

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 端点清单与配置 |
| GET | `/health` | 健康检测（grpc 连通、仿真运行状态） |
| GET | `/scripts` | 可用仿真脚本列表 |
| POST | `/start` | 启动仿真（`?script_name=`，已运行时 409） |
| POST | `/reset` | 重置仿真：终止→重新初始化（对局编号归 1） |
| GET | `/stop` | 停止仿真（保留行动历史） |
| GET | `/status` | 全局状态：`已结束` / `对局结果` / 资源快照 / 行动历史 |
| GET | `/raw` | 原始结构化状态（行为树 Agent 用）：white_usv_states / white_uav_states / white_observation |
| GET | `/obs` | 语义观察文本（Plain Text，供 LLM 类 Agent） |
| GET | `/legal_actions` | 合法动作空间（按类型分组） |
| POST | `/apply` | 注入动作列表，推进一个宏观步 |
| GET | `/result` | 对局结果与统计 |
| GET | `/game_log` | 对局日志（每步状态/事件/奖励） |

## /apply 请求体与返回

```json
// 请求
{"actions": [
  {"action_text": "white_usv1 移动 target_speed=15.0 target_course=90.0", "action_type": "move"},
  {"action_text": "white_uav1 从 white_usv1 起飞 target_speed=30.0 target_course=0.0", "action_type": "launch_uav"}
],
 "summary": {                 // 可选：决策摘要，仅记录进对局日志，不影响执行
   "units": {"white_usv1": {"kind": "usv", "status": {...}}},
   "actions_intent": [...], "previous_actions": [...]}}
// 返回
{"成功": true, "已队列": true,
 "执行结果": [{"序号": 1, "动作": "...", "成功": true, "跳过": false, "详情": "..."}],
 "执行统计": "2 个动作: 2 成功, 0 跳过"}
```

**注意**：`/apply` 任一动作失败即整批返回 HTTP 400（detail 含 `[动作N]` 失败序号），
此前动作已在仿真中执行。客户端（client.py）已内置按序号剔除重发，无需自行处理。

## 行为树接入（/bt 端点 — 远程 Harness 经 HTTP 驱动行为树）

决策分配层（Harness / MARL）部署在**远程服务器**上时，远程侧**无需部署行为树代码**：
行为树与平台执行器都在本机端口侧，远程侧只经 HTTP 调用 /bt 端点即可完成接入。
语义契约见仓库根《BT_HARNESS_INTERFACE_REFERENCE.md》（决策权边界、数据结构、
生命周期语义、动作映射、枚举全表），本节的 HTTP 字段与之逐一对应。

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/bt/task` | 下发平台任务（TaskCommand，任务参数即动作数值来源） |
| POST | `/bt/task/cancel` | 取消任务（重置该任务相关记忆，不销毁树） |
| GET | `/bt/tasks` | 当前各平台登记任务列表 |
| POST | `/bt/actions` | 行为树决策动作输出（每平台一次 tick，体可选带上一步 /apply 回执） |

### 决策循环（每宏观步）

```
开对局    POST /start 或 /reset（对局控制同原端口语义）
下发任务  POST /bt/task          —— 分配层决定 WHO+WHAT 时下发（勿每步重复）
每步循环  POST /bt/actions       —— 得到动作列表（行为树决定 HOW/NEXT PHASE）
          POST /apply            —— 整批执行动作，推进一个宏观步（30 仿真秒）
          POST /bt/actions（体带上一步 /apply 回执）—— 驱动树推进并输出下一步动作
```

### POST /bt/task

```json
// 请求（TaskCommand）
{"task_id": "white_usv1_black_usv9_intercept",
 "platform_id": "white_usv1", "platform_type": "USV",
 "task_type": "INTERCEPT_LOCK", "target_id": "black_usv9",
 "role": "default", "revision": 1, "priority": 0,
 "plan_id": "", "plan_revision": 1,
 "valid_from": null, "valid_until": null,
 "preemptible": true, "safety_override": false,
 "allow_local_reacquire": true, "max_search_time": 60.0,
 "constraints": {}}
// 返回
{"受理": "ACCEPTED", "平台": "white_usv1",
 "任务编号": "white_usv1_black_usv9_intercept", "消息": "新任务接受", "时间戳": ...}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `task_type` | str | `INTERCEPT_LOCK`/`ENGAGE_TARGET`/`HOLD_POSITION`（USV）；`COOPERATIVE_LOCK`/`SITUATION_UPDATE`/`RETURN_RECHARGE`/`HOLD_POSITION`（UAV） |
| `target_id` | str/null | 指派后**不可变**；丢失只允许局部 reacquire（同 target），超时交回分配层 |
| `revision` / `plan_revision` | int | 同 task_id 只认更高 revision（更新）；同 plan_id 更低 plan_revision 拒绝 |
| `preemptible` / `safety_override` | bool | 抢占规则：safety_override 或旧任务 preemptible 或新 priority 更高 |
| `valid_from` / `valid_until` | float/null | 生效窗口（仿真秒）；tick 时在窗口外不执行并反馈原因 |
| `constraints` | dict | 主要约束，可覆盖树默认值：`waypoint`(UAV 航点)、`base`(母舰)、`standoff_distance`、`approach_speed`、`orbit_speed`、`cruise_speed`、`takeoff_course`、`patrol_speed` |

`受理` 取值：`ACCEPTED` / `ACCEPTED_WITH_PREEMPTION` / `DUPLICATE_IGNORED` /
`STALE_REJECTED` / `EXPIRED` / `INVALID_PLATFORM` / `INVALID_TYPE` / `BUSY` /
`CANCELLED`（cancel 用）/ `NOT_FOUND`（cancel 用）。

### POST /bt/actions

```json
// 请求体（可选）：上一步 /apply 的执行结果回执，按动作文本关联
{"apply_results": [{"动作": "white_usv1 移动 target_speed=20 target_course=90",
                    "成功": true, "跳过": false}]}
// 返回
{"成功": true, "tick": 12,
 "动作": [{"action_text": "white_usv1 移动 target_speed=20 target_course=92.6",
          "action_type": "move"}],
 "任务反馈": [{"platform_id": "white_usv1", "task_id": "...",
             "status": "RUNNING", "phase": "approach",
             "target_id": "black_usv9", "target_visible": true,
             "target_confidence": 1.0, "need_reallocation": false,
             "reason_code": "none"}],
 "平台": {"white_usv1": {"root_status": "RUNNING",
                       "active_branch": "approach", "动作数": 1}}}
```

- `动作` 为可直接整批 POST /apply 的 payload；同平台同 tick 每控制通道至多 1 条
- `任务反馈.need_reallocation=true` 时分配层应重新分配（原因码见 `reason_code`：
  `target_lost_timeout`/`blocked`/`expired`/`unreachable` 等）
- 回执映射：`跳过`→REJECTED、成功→ACCEPTED（写入行为树 safety 反馈；
  被拒动作下一 tick 改 HOLD/fallback，不再重复被拒原语）

### 网络要求

远程 Harness 服务器需能访问本 API 的 HTTP 端口（默认 8000，监听 0.0.0.0）：
同一内网用内网 IP；跨网需公网 IP / 端口映射 / 内网穿透。设置 `API_HOST`
环境变量（对外地址）后，`/docs` 可提供交互式接口文档。
另外注意：本 API 内部经 gRPC 连仿真后端（`SIM_HOST`，默认 192.168.252.41:6000），
与远程 Harness 无关。

### 备选：进程内接入（行为树部署到远程侧）

若远程侧希望按《BT_HARNESS_INTERFACE_REFERENCE.md》§9 的方式进程内
`submit_task → tick → /apply`，把 `behavior_tree/harness_interface.py` 与
`harness_trees.py`（纯标准库、零依赖）拷到远程侧即可，状态获取走
`GET /raw`，动作执行走 `POST /apply`。此模式下远程侧需自行组装
`ExecutionContext`（参考 `pomdp_api/routes/executive.py::_build_contexts`）。
推荐优先使用 HTTP 接入（上面主流程），行为树状态保持在端口侧、随对局重置，
双方只需对齐 HTTP 契约。

## 动作类型

| 类型 | 格式 | 说明 |
|---|---|---|
| `move` | `{单位} 移动 target_speed={值} target_course={值}` | USV 机动（0-100 m/s，0-360°） |
| `fly` | `{单位} 飞行 target_speed={值} target_course={值}` | UAV 飞行 |
| `lock` | `{单位} 锁定 {目标}` | 锁定目标（需雷达捕获且 40km 内） |
| `launch_uav` | `{UAV} 从 {母船} 起飞 target_speed={值} target_course={值}` | 起飞 UAV |
| `land_uav` | `{UAV} 降落到 {母船}` | 降落 UAV |
| `noop` | `空操作，等待一个宏观步` | 空操作（仅推进时间） |

## Python 客户端（client.py）

供决策 Agent 直接调用，封装了地址/端口/409 已运行/400 失败重发等协议细节：

```python
from pomdp_api.client import SimAPIClient, SimAPIError

api = SimAPIClient("http://127.0.0.1:8000")   # 默认读环境变量 API_URL
api.start("测试用例1")          # 已运行(409)时自动重置
raw = api.raw()                 # 原始状态（决策依据）
api.status()                    # 已结束 / 对局结果
results = api.apply([...])      # 与入参对齐的执行结果；空列表自动下发 noop
api.reset("测试用例1")          # 重开一局
```

## 常见问题

| 现象 | 原因与处理 |
|---|---|
| 启动后端报循环导入 `ImportError: cannot import name 'entity'` | 用了 base 环境（Python 3.14）。必须 `conda activate hsystem_env`（Python 3.8） |
| `ModuleNotFoundError: No module named 'pomdp_api'` | 旧代码或残留缓存。app.py 已内置路径引导，两种启动方式均可；若仍出现，删除 `pomdp_api/__pycache__` 后重试 |
| 重置/启动报 `ENGINE_SIM_RUNNING` | 引擎终止是异步的，API 已自动等待重试（最多 3 次）。仍失败时稍等几秒再试 |
| `ERROR 409 仿真已在运行中` | 已有对局在跑。客户端会自动转 /reset；手动调 API 时直接 POST /reset |
| 后端端口 6000/6001-6005 被占用 | 有残留 base_server 进程。先 `pkill -f base_server` 再启动 |
| `/apply` 返回 400 `[动作N] xxx` | 该条指令非法（单位已摧毁/已在空中/目标不存在等）。客户端会自动剔除该条重发其余 |

## 文件

| 文件 | 职责 |
|---|---|
| `app.py` | 启动入口（挂载路由，uvicorn :8000，经 `python -m pomdp_api.app` 启动） |
| `shared.py` | 公共层：gRPC 连接、状态管理、动作解析与执行、对局日志 |
| `checks.py` | 动作执行前判定（存活/在甲板/目标存在等） |
| `routes/` | 每个端点一个路由文件 |
| `client.py` | API 客户端（供行为树 Agent 等外部决策方使用） |
| `logger.py` | 日志配置 |
| `API使用说明.md` | 本文档 |

## 日志

日志统一放在仓库根目录 `logs/`（与 pomdp_api 平级，方便统一收集）：

```
logs/
├── runtime/                              ← 服务运行日志（10MB×3 自动轮转）
│   ├── sim_api.log                       业务日志：对局生命周期、指令执行明细与失败原因、异常
│   └── access.log                        HTTP 访问日志：方法/路径/状态码/耗时（审计）
└── games/                                ← 对局数据日志（JSON，每局一个文件）
    └── game_{episode_id}_{timestamp}.json
```

**三种日志的分工**：

| 日志 | 看什么 | 典型内容 |
|---|---|---|
| `sim_api.log` | 服务发生了什么 | `POST /apply`、`white_uav1 从 white_usv1 起飞 speed=30.0 course=0.0`、后端异常堆栈 |
| `access.log` | 谁调了哪个端口 | `POST /apply → 200 (52.3 ms)` |
| `games/*.json` | 对局数据本身（复盘/训练） | 每步：时间轴、动作与结果、单位快照、敌情、事件、**决策摘要**；终局：胜负、存活统计、**失败原因统计** |

games 日志中的决策摘要由决策客户端随 `/apply` 附带（`summary` 字段）：
每单位决策状态（接近/环绕/盘旋、任务进度）、本步动作意图、
上一步完整执行结果（**含被仿真拒绝的失败项**——失败项不会出现在返回的
"执行结果"里，靠摘要补全）。终局 `final_stats.action_fail_stats`
按失败原因聚合统计（如"已摧毁 3 次 / 已在甲板上 1 次"）。

**对局文件以 reset 为分割**：每局一个文件，文件名带时间戳不覆盖——
对局结束、主动停止、或被 reset 打断时都会自动封存（JSON 中 `closed_by`
字段标记封存原因：对局结束 / 对局停止 / 对局重置）。所有文件全部保留，
如需清理请人工删除；无任何步数的空对局不落盘。

