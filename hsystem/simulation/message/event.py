""" 事件定义
"""
from .. import algorithm as alg
from .. import core


class EventTakeOff(core.message.Content):
    """ 飞机起飞事件
    """
    def __init__(self, plane, flag):
        self.plane = plane
        assert flag in ["Failure", "Success"]
        self.flag = flag

class EventReturnToBase(core.message.Content):
    """ 飞机等航程不足，需返回基地事件
    """
    def __init__(self, flag):
        assert flag in ["Begin", "End"]
        self.flag = flag # Begin 或 End

class EventLandOn(core.message.Content):
    """ 飞机着陆事件
    """
    def __init__(self, plane, flag):
        self.plane = plane
        assert flag in ["Failure", "Success"]
        self.flag = flag

class EventManeuver(core.message.Content):
    """ 执行某种机动对应的事件，包括抵达某个航路点的事件
    """
    def __init__(self, flag, point=None):
        self.flag = flag
        self.point = point

class EventDetectFirst(core.message.Content):
    ''' 首次探测目标事件
    '''
    def __init__(self, target, sensor):
        self.target = target
        self.sensor = sensor