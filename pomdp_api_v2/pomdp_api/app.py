"""
仿真 POMDP API

宏观步决策循环:
  1. GET  /status         → 检查 已结束 / 等待指令
  2. GET  /obs             → 语义观察（Plain Text）
  3. GET  /legal_actions   → 合法动作空间（JSON 字符串数组 + 参数说明）
  4. Agent 策略推演
  5. POST /apply           → 注入动作 → 环境推进 → 到达下一决策点
  6. 循环 1-5 直到 已结束=true

端点:
  GET  /                 服务信息与端点清单
  GET  /health            健康检测
  GET  /scripts           可用仿真脚本列表
  POST /start             启动新仿真（episode_id 递增，清空历史）
  GET  /stop              停止当前仿真（保留行动历史）
  POST /reset             重置仿真（终止 → 清理 → 重新初始化，episode_id 重置为 1）
  GET  /status            全局状态与时间轴同步（含资源快照与行动历史镜像）
  GET  /obs               语义观察（Plain Text，状态/锁定/冻结/存活损毁）
  GET  /legal_actions     合法动作空间（JSON 字符串数组 + 参数说明）
  POST /apply             注入动作列表 → 推进一个宏观步
  GET  /result            对局结果分析（含完整行动历史）
  GET  /game_log          对局日志（含每步状态/事件/奖励）
  POST /bt/task           行为树任务下发（Harness → BT，见 BT_HARNESS_INTERFACE_REFERENCE.md）
  POST /bt/task/cancel    行为树任务取消
  GET  /bt/tasks          行为树各平台登记任务列表
  POST /bt/actions        行为树决策动作输出（作用类似 /legal_actions，经 /apply 执行）

监听端口: 8000 (环境变量 APP_PORT)
后端通信: BaseServer gRPC (6000)
启动:     python app.py（本目录）或 python -m pomdp_api.app（仓库根目录），两种均可

文件结构:
  app.py           启动入口，挂载路由
  shared.py        公共层：配置、模型、gRPC、状态、业务函数
  checks.py        动作执行前判定
  logger.py        日志配置
  routes/          路由层（每个端点一个文件）
"""

import os
import sys
import time

# 包风格导入(pomdp_api.xxx)需要仓库根目录在 sys.path 中。
# 无论在本目录 python app.py，还是在仓库根目录 python -m pomdp_api.app 都能启动。
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware

from pomdp_api.shared import ENABLE_DOCS, _HOST, _PORT, APP_PORT, _USER_NAME, _API_HOST, MACRO_STEP_DURATION
from pomdp_api.logger import _access_log

app = FastAPI(
    title="仿真 API",
    description="军事仿真推演系统 POMDP 语义交互接口",
    version="1.0",
    docs_url="/docs" if ENABLE_DOCS else None,
    redoc_url="/redoc" if ENABLE_DOCS else None,
)
app.add_middleware(GZipMiddleware, minimum_size=512)


@app.middleware("http")
async def log_requests(request, call_next):
    """访问审计：记录每个 HTTP 请求的方法/路径/状态码/耗时 → logs/runtime/access.log"""
    start = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start) * 1000
    _access_log.info("%s %s → %d (%.1f ms)",
                     request.method, request.url.path,
                     response.status_code, duration_ms)
    return response

# ─── 挂载路由 ─────────────────────────────────────────

from pomdp_api.routes.status import router as status_router
from pomdp_api.routes.obs import router as obs_router
from pomdp_api.routes.actions import router as actions_router
from pomdp_api.routes.control import router as control_router
from pomdp_api.routes.result import router as result_router
from pomdp_api.routes.executive import router as executive_router

app.include_router(status_router)
app.include_router(obs_router)
app.include_router(actions_router)
app.include_router(control_router)
app.include_router(result_router)
app.include_router(executive_router)

# ─── 启动 ─────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    print("=" * 56)
    print("  仿真 POMDP API")
    print(f"  监听: 0.0.0.0:{APP_PORT}")
    print(f"  后端: {_HOST}:{_PORT}")
    print(f"  用户: {_USER_NAME}")
    print(f"  日志: sim_api.log")
    if _API_HOST:
        print(f"  文档: http://{_API_HOST}:{APP_PORT}/docs")
    else:
        print("  ⚠ 未设置 API_HOST，/docs 链接不可用，请设置后重启")
    print(f"  宏观步步长: {MACRO_STEP_DURATION}s（仿真秒数）")
    print("=" * 56)
    uvicorn.run(app, host="0.0.0.0", port=APP_PORT, log_level="info")
