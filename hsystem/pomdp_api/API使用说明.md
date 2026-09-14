# 仿真 POMDP API

## 激活虚拟环境 + 设置环境变量

```bash
source /root/miniconda3/bin/activate
conda activate hsystem_env
export PYTHONPATH="/root/autodl-tmp/hsystem/hsystem:${PYTHONPATH}"
```


## 启动(~/autodl-tmp/hsystem目录下)


```bash
# 1. 后端（simserver/ 目录下）
cd hsystem/simserver
python base_server.py

# 2. API（pomdp_api/ 目录下）
cd hsystem/hsystem/pomdp_api
python main.py
```

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `SIM_HOST` | `116.136.52.196` | 后端 IP |
| `SIM_PORT` | `6000` | gRPC 端口 |
| `APP_PORT` | `8000` | API 端口 |
| `MACRO_STEP` | `30` | 宏观步步长（仿真秒） |

## 决策循环

```
GET  /status         → 已结束 / 等待指令
GET  /obs            → 语义观察（Plain Text）
GET  /legal_actions  → 合法动作空间
POST /apply          → 注入动作，推进一个宏观步
重复直到 已结束=true
```

## 端点

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 端点清单 |
| GET | `/health` | 健康检测 |
| GET | `/scripts` | 可用脚本列表 |
| POST | `/start` | 启动仿真，episode_id 递增 |
| POST | `/reset` | 重置仿真 |
| GET | `/stop` | 停止仿真 |
| GET | `/status` | 全局状态（含资源快照、行动历史） |
| GET | `/obs` | 语义观察文本（Plain Text） |
| GET | `/legal_actions` | 合法动作空间（按类型分组） |
| POST | `/apply` | 注入动作列表 |
| GET | `/result` | 对局结果与统计 |
| GET | `/game_log` | 对局日志（每步状态/事件/奖励） |

## /apply 请求体

```json
{
  "actions": [
    {"action_text": "white_usv1 移动 target_speed=15.0 target_course=90.0", "action_type": "move"},
    {"action_text": "white_uav1 从 white_usv1 起飞 target_speed=20.0 target_course=45.0", "action_type": "launch_uav"}
  ]
}
```

## 动作类型

| 类型 | 格式 | 说明 |
|---|---|---|
| `move` | `{单位} 移动 target_speed={值} target_course={值}` | USV 机动 |
| `fly` | `{单位} 飞行 target_speed={值} target_course={值}` | UAV 飞行 |
| `lock` | `{单位} 锁定 {目标}` | 锁定目标（需雷达捕获） |
| `launch_uav` | `{UAV} 从 {母船} 起飞 target_speed={值} target_course={值}` | 起飞 UAV |
| `land_uav` | `{UAV} 降落到 {母船}` | 降落 UAV |
| `noop` | `空操作，等待一个宏观步` | 空操作 |

## 日志

```
pomdp_api/api_logs/
├── runtime/                              ← API 运行日志
│   └── sim_api.log
└── games/                                ← 对局日志（每局一个 JSON）
    └── game_{episode_id}_{timestamp}.json
```
