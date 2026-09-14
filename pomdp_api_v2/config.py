"""
连接配置（服务器版 pomdp_api_v2 专用，环境变量可覆盖）

部署在 /root/autodl-tmp/hsystem/pomdp_api_v2/，与旧版 main.py 的
pomdp_api 并存（端口 8001，不动原有文件）。
"""
import os

SIM_HOST = os.getenv("SIM_HOST", "127.0.0.1")      # 本机仿真后端
SIM_PORT = os.getenv("SIM_PORT", "6000")
SIM_USER = os.getenv("SIM_USER", "admin")
API_URL = os.getenv("API_URL", "http://127.0.0.1:8001")
APP_PORT = int(os.getenv("APP_PORT", "8001"))       # 新版 API 监听 8001
API_HOST = os.getenv("API_HOST", "")
STEP_DELAY = float(os.getenv("STEP_DELAY", "0.5"))
SHOW_ACTIONS = os.getenv("SHOW_ACTIONS", "0") == "1"
