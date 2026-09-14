# cython:language_level=3
# distutils: language=c++
from simulation.core.entity cimport Entity

cdef class HEAD:
    cdef public Entity send
    cdef public Entity recv
    cdef public float when

cdef class MESSAGE:
    cdef public HEAD head
    cdef public body

cdef class STATE:
    cdef public str state

cdef class FUNC:
    cdef public func
    cdef public args

cdef class Msg:
    cdef public Entity src
    cdef public Entity dst
    cdef public float send_time
    cdef public bint isignored
    cdef public content

cdef class Cmd:
    cdef public Entity src
    cdef public Entity dst
    cdef public float send_time
    cdef public bint isignored
    cdef public content

cdef class Event:
    cdef public Entity src
    cdef public Entity dst
    cdef public float send_time
    cdef public content

cdef class Task:
    cdef public Entity src
    cdef public Entity dst
    cdef public float send_time
    cdef public bint isignored
    cdef public content

cdef class Content:
    cdef public str text

cdef class MsgContent(Content):
    """ 以消息的形式发送内容 """


cdef class MsgTrack(Content):
    """ 情报信息 """
    cdef public track #TODO: type

#--------命令---------------------------
cdef class CmdSensorTurnOn(Content):
    "传感器开机指令"

cdef class CmdSensorTurnOff(Content):
    "传感器关机指令"

cdef class CmdMotorChangeSpeed(Content):
    "机动组件改变速度指令"
    cdef public float speed

cdef class CmdMotorChangeVelocity(Content):
    "机动组件改变速度（三维）指令"
    cdef public velocity


cdef class CmdMotorChangeCourse(Content):
    "机动组件改变航向指令"
    cdef public float az


cdef class CmdMotorChangeHeight(Content):
    "机动组件改变高度指令"
    cdef public float height

#--------事件---------------------------
cdef class EventHit(Content):
    "被击中事件"


cdef class EventCollided(Content):
    "发生碰撞事件"
    cdef public Entity foe

cdef class EventNextFun(Content):
    cdef public str name
    cdef public func
    cdef public args


