""" 传感器探测到的点迹/航迹信息载体（类似消息格式）
"""
from .. import algorithm as alg


class SensorTrack(object):
    def __init__(self, target, sensor, when, mode):
        self.target = target # 真实目标
        self.sensor = sensor # 探测到该目标的传感器
        self.when = when # 探测时间,ms
        self.mode = mode # 探测模式，具体由各子类定义，一般分为active(主动), passive(被动), hybrid(混合)


class RadarTrack(SensorTrack):
    def __init__(self, target, sensor, when, mode, coords=None, velocity=None, az=None, QoI=None, flag="undefined"):
        super().__init__(target, sensor, when, mode)
        if coords is not None:
            self.coords = coords.copy()
        if velocity is not None:
            self.velocity = velocity.copy()
        self.az = az # 被动或混合模式下有效
        self.QoI = QoI # 情报信息质量
        self.flag = flag #  "point": 点迹，"track":航迹，"undefined":未定义