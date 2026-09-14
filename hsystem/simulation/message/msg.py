""" 一般消息定义
"""
from .. import core



class MsgLandOnRequset(core.message.Content):
    """ 飞机着陆请求 """
    def __init__(self, plane):
        self.plane = plane


class MsgLandOnEcho(core.message.Content):
    """ 飞机着陆请求的回应 """
    def __init__(self, flag):
        assert flag in ["Yes", "No"]
        self.flag = flag # Yes 或 No


class MsgFlyLead(core.message.Content):
    "飞机飞行引导消息"
    def __init__(self, pos):
        self.pos = pos


class MsgCmd(core.message.Content):
    " 以消息的形式发送指令 "
    def __init__(self, cmd, **kwargs):
        self.cmd = cmd
        self.kwargs = kwargs


class MsgTargetInfo(core.message.Content):
    """  """
    def __init__(self, target, track, src):
        self.target = target
        self.track = track
        self.src = src


class MsgPlatformInfo(core.message.Content):
    """  """
    def __init__(self, platform_info, src):
        self.platform_info = platform_info
        self.src = src

class MsgStateInfo(core.message.Content):
    """  """
    def  __init__(self, name, state_info):
        self.name = name
        self.state_info = state_info