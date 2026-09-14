"""
日志模块 — 统一管理日志路径、格式与轮转

目录结构（仓库根目录 logs/，与 pomdp_api 平级）:
  logs/
  ├── runtime/                          ← 服务运行日志（文本，10MB×3 自动轮转）
  │   ├── sim_api.log                   业务日志：对局生命周期、指令执行明细、异常
  │   └── access.log                    HTTP 访问日志：方法/路径/状态码/耗时
  └── games/                            ← 对局数据日志
      ├── game_records.log              ← 合并格式文本（人/LLM 阅读）: 每局一节，
      │                                    episode=N 起、RESET 分割，外层数据与结果
      │                                    + 内嵌"动作:"块（空操作/飞行等，带单位名称、
      │                                    速度、航向）；对局封存时追加
      └── game_{episode_id}_{时间戳}.json  ← 每局完整 JSON（每步状态/动作结果/敌情/
                                           事件/决策摘要），供复盘与训练

内容分工:
  sim_api.log   服务本身发生了什么（start/reset/指令成功失败原因/后端异常）
  access.log    谁在什么时间调了哪个端点（审计用）
  games/*.json  对局数据本身（每步状态/动作结果/敌情/事件/决策摘要），供复盘与训练
  game_records.log 合并格式对局日志（每局 episode=N 起、RESET 分割，人/LLM 阅读）
"""

import os
import logging
from logging.handlers import RotatingFileHandler

_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "logs")
_RUNTIME_LOG_DIR = os.path.join(_LOG_DIR, "runtime")
_GAME_LOG_DIR = os.path.join(_LOG_DIR, "games")
os.makedirs(_RUNTIME_LOG_DIR, exist_ok=True)
os.makedirs(_GAME_LOG_DIR, exist_ok=True)


def _new_logger(name: str, filename: str) -> logging.Logger:
    """创建带文件轮转 + 控制台输出的 logger"""
    lg = logging.getLogger(name)
    if lg.handlers:
        return lg  # 防止重复挂载
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S")
    fh = RotatingFileHandler(os.path.join(_RUNTIME_LOG_DIR, filename),
                             encoding="utf-8",
                             maxBytes=10 * 1024 * 1024, backupCount=3)
    fh.setFormatter(fmt)
    lg.addHandler(fh)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    lg.addHandler(sh)
    lg.setLevel(logging.INFO)
    lg.propagate = False  # 各 logger 独立落盘，避免 access 日志混入业务日志
    return lg


# 业务日志: 对局生命周期、指令执行明细、异常
_log = _new_logger("pomdp_api", "sim_api.log")

# HTTP 访问日志: 方法/路径/状态码/耗时（app.py 中间件写入）
_access_log = _new_logger("pomdp_api.access", "access.log")
