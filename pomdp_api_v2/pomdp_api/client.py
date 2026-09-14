"""
POMDP API 客户端 — 供外部决策 Agent 使用

封装 HTTP 端点与协议细节（地址/端口、409 已运行、/apply 单条失败整批 400
的容错重发），决策侧只调用语义方法，不接触传输层。

用法:
    from pomdp_api.client import SimAPIClient, SimAPIError

    api = SimAPIClient("http://127.0.0.1:8000")
    api.start("测试用例1")
    raw = api.raw()
    results = api.apply([{"action_text": "white_usv1 移动 target_speed=15 "
                                        "target_course=90",
                          "action_type": "move"}])
"""

import re
import time
from typing import Optional

import requests

NOOP = {"action_text": "空操作", "action_type": "noop"}


class SimAPIError(Exception):
    """连接失败或 API 返回错误（HTTP 400 不在其列，由 apply 内部消化）"""


class SimAPIClient:

    def __init__(self, api_url: Optional[str] = None):
        if api_url is None:
            # 连接配置集中在仓库根 config.py（惰性导入避免路径依赖）
            from config import API_URL
            api_url = API_URL
        self.api_url = api_url.rstrip("/")

    # ================================================================
    # 传输层
    # ================================================================

    def _request(self, method: str, path: str, **kw):
        """发送请求。连接失败抛 SimAPIError；HTTP 错误原样返回响应由调用方处理"""
        timeout = kw.pop("timeout", 60)
        try:
            return requests.request(method, self.api_url + path,
                                    timeout=timeout, **kw)
        except requests.RequestException as e:
            raise SimAPIError(f"连接 {self.api_url} 失败: {e}")

    @staticmethod
    def _json_ok(resp, what: str) -> dict:
        """2xx → JSON; 其余抛 SimAPIError（detail 带入错误信息）"""
        if resp.status_code != 200:
            try:
                detail = resp.json().get("detail", resp.text)
            except ValueError:
                detail = resp.text
            raise SimAPIError(f"{what} 失败 ({resp.status_code}): {detail}")
        return resp.json()

    # ================================================================
    # 对局管理
    # ================================================================

    def start(self, script: str) -> dict:
        """启动仿真；已有对局在跑(409)时重置（/reset 自带重新初始化，无需再 /start）"""
        resp = self._request("POST", "/start", params={"script": script})
        if resp.status_code == 409:
            return self.reset(script)
        return self._json_ok(resp, "启动仿真")

    def reset(self, script: str) -> dict:
        return self._json_ok(
            self._request("POST", "/reset", params={"script": script}),
            "重置仿真")

    def status(self) -> dict:
        """全局对局状态。字段: 已结束 / 对局结果 / 资源快照 / 脚本 / 开局时间 ..."""
        return self._json_ok(self._request("GET", "/status"), "状态查询")

    def status_or_none(self) -> Optional[dict]:
        """对局状态；仿真未启动（404）或连接失败时返回 None，不抛异常。

        供跟随模式的 Agent 轮询：端口未开对局时安静待命。
        """
        try:
            return self.status()
        except SimAPIError:
            return None

    def raw(self) -> dict:
        """原始仿真状态（结构化 JSON）: white_usv_states / white_uav_states /
        white_observation"""
        return self._json_ok(self._request("GET", "/raw"), "状态获取")

    # ================================================================
    # 动作下发
    # ================================================================

    def apply(self, actions: list, summary: Optional[dict] = None) -> list:
        """下发动作列表，返回与 actions 一一对齐的执行结果

        summary: 决策摘要（每单位状态、动作意图、上一步执行结果等），
                 随请求附带，仅由 API 记录进对局日志，不影响执行。

        协议要点:
          - /apply 任一动作失败即整批 400（detail 含 "[动作N]" 失败序号），
            此前动作已在仿真中执行；按序号剔除失败项后重发其余，避免整批丢失
          - 连接失败无法定位时剔除第一条重试，不产生死循环
          - 空列表时下发一次 noop，推进仿真一个宏观步
        """
        if not actions:
            # 空列表时下发一次 noop，推进仿真一个宏观步
            try:
                self._request("POST", "/apply",
                              json={"actions": [NOOP], "summary": summary})
            except SimAPIError:
                pass
            return []

        results: list = [None] * len(actions)
        pending = list(range(len(actions)))
        while pending:
            payload = [actions[i] for i in pending]
            try:
                resp = self._request("POST", "/apply",
                                     json={"actions": payload, "summary": summary})
            except SimAPIError as e:
                i = pending.pop(0)
                results[i] = {"成功": False, "跳过": False, "详情": str(e)}
                time.sleep(1)
                continue
            if resp.status_code == 200:
                for i, item in zip(pending, resp.json().get("执行结果", [])):
                    results[i] = item
                return results
            # 400: detail 形如 "[动作3] xxx" → 定位失败项
            try:
                detail = resp.json().get("detail", "")
            except ValueError:
                detail = ""
            m = re.search(r"动作(\d+)", detail or "")
            bad = (int(m.group(1)) - 1) if m else 0
            bad = min(bad, len(pending) - 1)
            i = pending.pop(bad)
            results[i] = {"成功": False, "跳过": False, "详情": detail or "API 拒绝"}
            if not pending:
                return results
        return results
