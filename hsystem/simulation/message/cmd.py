""" 命令/指令定义
"""
from .. import core


class CmdSystemTurnOn(core.message.Content):
    ""
    def __init__(self):
        super().__init__("")


class CmdJammerTurnOn(core.message.Content):
    ""
    def __init__(self):
        super().__init__("")


class CmdJammerTurnOff(core.message.Content):
    ""
    def __init__(self):
        super().__init__("")

class CmdFlyPlane(core.message.Content):
    "放飞飞机指令"
    def __init__(self, num=1):
        super().__init__("")
        self.num = num