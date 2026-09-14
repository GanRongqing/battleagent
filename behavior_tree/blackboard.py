"""黑板 — 树内共享记忆（含任务键与执行上下文）"""

from typing import Any, Dict


class Blackboard:
    def __init__(self) -> None:
        self._d: Dict[str, Any] = {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._d.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._d[key] = value
