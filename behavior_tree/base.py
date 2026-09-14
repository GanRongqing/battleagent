"""节点定义 — 行为树框架（Status/Node/Selector/Sequence/Behavior/BehaviorTree，含 memory）"""

from typing import Callable, List, Optional

from .status import Status
from .blackboard import Blackboard


class Node:
    """节点基类"""

    def __init__(self, name: str = "node") -> None:
        self.name = name

    def tick(self, bb: Blackboard) -> Status:
        raise NotImplementedError

    def reset(self) -> None:
        """清 memory 分支（默认无状态）"""


class Behavior(Node):
    """叶子行为 — 闭包实现具体逻辑"""

    def __init__(self, name: str, fn: Callable[[Blackboard], Status]) -> None:
        super().__init__(name)
        self._fn = fn

    def tick(self, bb: Blackboard) -> Status:
        return self._fn(bb)


class Sequence(Node):
    """顺序节点 — 依次执行子节点；FAILURE 即失败，RUNNING 即挂起

    memory=True: 记住 RUNNING 子节点下标，下次从该子节点继续（如
    engage 序列：SendLock 发过一次后不再重复）。"""

    def __init__(self, name: str, children: List[Node],
                 memory: bool = False) -> None:
        super().__init__(name)
        self.children = children
        self.memory = memory
        self._idx = 0

    def tick(self, bb: Blackboard) -> Status:
        start = self._idx if self.memory else 0
        for i in range(start, len(self.children)):
            st = self.children[i].tick(bb)
            if st == Status.FAILURE:
                if self.memory:
                    self._idx = 0
                return Status.FAILURE
            if st == Status.RUNNING:
                if self.memory:
                    self._idx = i
                return Status.RUNNING
        if self.memory:
            self._idx = 0
        return Status.SUCCESS

    def reset(self) -> None:
        self._idx = 0
        for c in self.children:
            c.reset()


class Selector(Node):
    """选择节点 — 依次尝试子节点；任一非 FAILURE 即通过（重查语义）

    memory=True: 记住 RUNNING 子节点下标（如 reacquire 持续执行）。"""

    def __init__(self, name: str, children: List[Node],
                 memory: bool = False) -> None:
        super().__init__(name)
        self.children = children
        self.memory = memory
        self._idx = 0

    def tick(self, bb: Blackboard) -> Status:
        start = self._idx if self.memory else 0
        for i in range(start, len(self.children)):
            st = self.children[i].tick(bb)
            if st != Status.FAILURE:
                if self.memory:
                    self._idx = i
                return st
        if self.memory:
            self._idx = 0
        return Status.FAILURE

    def reset(self) -> None:
        self._idx = 0
        for c in self.children:
            c.reset()


class BehaviorTree:
    """树实例 — 树记忆在实例内部（blackboard），不暴露树外"""

    def __init__(self, root: Node, blackboard: Optional[Blackboard] = None) -> None:
        self.root = root
        self.blackboard = blackboard or Blackboard()
        self.active_task = None     # 当前任务命令（submit_task 写入）

    def tick(self) -> Status:
        return self.root.tick(self.blackboard)

    def reset(self) -> None:
        self.root.reset()
