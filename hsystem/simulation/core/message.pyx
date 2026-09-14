
# define messages generated and processed by core.engine and core.entity
"""消息的命名习惯
message表示最底层的消息
head代表其消息头
body代表其消息体
msg/cmd/event分别表示body的三种类型,有时也用msg代表三者
content表示更具体的内容
"""
# FMT = lambda fmt: (lambda self: fmt.format(message=self))

cdef ctx(message, formatter):
    """ Format message context. """
    def inner(message):
        content = formatter.format(message=message)
        if isinstance(message, MESSAGE):
            content = "[{}]".format(id(message)) + content
        return content
    return inner(message)

cdef class HEAD:
    def __init__(self, send, recv, when):
        self.send = send  # 有可能是Router及其子类
        self.recv = recv
        self.when = when
    
    def __str__(self):
        return ctx(self, "from {message.send} to {message.recv} at {message.when}")

    def __doc__(self):
        return """ Header for message transimtting.

Attributes
----------
send : core.arch.Entity.ZIP
    Zipcode of the unit that will send the message.
recv : core.arch.Entity.ZIP
    Zipcode of the unit that will receive the message.
when : int (millisecond)
    Timestamp when the message is sent (millisecond).
"""

cdef class MESSAGE:

    def __init__(self, head, body):
        self.head = head
        self.body = body

    def __str__(self):
        return ctx(self, "[|head> {message.head} |body> {message.body}]")

    def __doc__(self):
        return """ Packaged message structure.

A packaged message is comprised of a head part and a body part.
Head is generated and added by the engine and body is the message or command
itself.

Attributes
----------
message.head.send : core.arch.Entity.ZIP
    Zipcode of the unit that will send the message.
message.head.recv : core.arch.Entity.ZIP
    Zipcode of the unit that will receive the message.
message.head.when : int (millisecond)
    Timestamp when the message is sent (millisecond).
message.body : message or command
    Message and command content that will be sent.
"""

#状态消息
cdef class STATE:

    def __init__(self, state):
        self.state = state

    def __str__(self):
        return ctx(self, "STATE: {message.state}")

    def __doc__(self):
        return """状态消息,支撑转态转移机制的实现"""

#函数消息
cdef class FUNC:

    def __init__(self, func, args):
        self.func = func
        self.args = args

    def __str__(self):
        return ctx(self, "func: {message.func}, args: {message.args}")

    def __doc__(self):
        return """函数消息,通过消息机制支撑函数的延时执行"""

#一般消息
cdef class Msg:
    '''一般消息

        该类的对象通过Component对象的send_message发送，通过通信设备发送的
        Args:
        src: 发送该消息的真实发送者，可能与msg.head.send不一致，因为存在通信设备转发
        dst:发送该消息的真实接收者，可能与msg.head.recv不一致，因为存在通信设备转发
        send_time:发送该消息的真实时间，可能与msg.head.when不一致，因为存在通信排队时延，且单位为s
        isignored:如果通信条件不满足，是否直接忽略
        content:消息内容,为类或命名元组的对象，其类名为分发给不同函数处理的依据，类名均以Msg开头
    '''
    def __init__(self, src, dst, send_time, isignored, content):
        self.src = src
        self.dst = dst
        self.send_time = send_time
        self.isignored = isignored
        self.content = content

    def __getattr__(self, attr):
        return getattr(self.content, attr)


#命令
cdef class Cmd:
    '''命令

        该类的对象通过Component对象的send_command发送，不通过通信设备发送，仅能在Unit内部传递，且是瞬时传递
        Args:
        src: 发送该命令的真实发送者，与msg.head.send一致
        dst:发送该命令的真实接收者，与msg.head.recv一致
        send_time:发送该命令的真实时间，与msg.head.when一致，但单位为s
        isignored:如果通信条件不满足，是否直接忽略
        content:命令内容,为类或命名元组的对象，其类名为分发给不同函数处理的依据，类名均以Cmd开头
    '''
    def __init__(self, src, dst, send_time, isignored, content):
        self.src = src
        self.dst = dst
        self.send_time = send_time
        self.isignored = isignored
        self.content = content

    def __getattr__(self, attr):
        return getattr(self.content, attr)


#事件（借鉴Xsim中的概念，为不需要探知的真实事件）
cdef class Event:
    '''事件

        该类的对象通过Component对象的send_event发送，不通过通信设备发送，可在Unit内或Unit间传递，可以瞬时也可以延时
        Args:
        src: 发送该事件的真实发送者，与msg.head.send一致
        dst:发送该事件的真实接收者，与msg.head.recv一致
        send_time:发送该事件的真实时间，与msg.head.when一致，但单位为s
        content:事件内容,为类或命名元组的对象，其类名为分发给不同函数处理的依据，类名均以Event开头
    '''
    def __init__(self, src, dst, send_time, content):
        self.src = src
        self.dst = dst
        self.send_time = send_time
        self.content = content

    def __getattr__(self, attr):
        return getattr(self.content, attr)


#任务
cdef class Task:
    '''任务

        该类的对象通过组件Commander对象的send_task发送，通过通信设备发送的
        Args:
        src: 发送该消息的真实发送者，可能与msg.head.send不一致，因为存在通信设备转发
        dst:发送该消息的真实接收者，可能与msg.head.recv不一致，因为存在通信设备转发
        send_time:发送该消息的真实时间，可能与msg.head.when不一致，因为存在通信排队时延，且单位为s
        isignored:如果通信条件不满足，是否直接忽略
        content:任务内容,为类或命名元组的对象，其类名为分发给不同函数处理的依据，类名均以Task开头
    '''
    def __init__(self, src, dst, send_time, isignored, content):
        self.src = src
        self.dst = dst
        self.send_time = send_time
        self.isignored = isignored
        self.content = content

    def __getattr__(self, attr):
        return getattr(self.content, attr)


# 内容基类
cdef class Content:
    def __init__(self, text=""):
        self.text = text


#--------一般消息-----------------------
cdef class MsgContent(Content):
    pass

cdef class MsgTrack(Content):
    def __init__(self, track):
        self.track = track


#--------命令---------------------------
cdef class CmdSensorTurnOn(Content):
    def __init__(self):
        super().__init__("")


cdef class CmdSensorTurnOff(Content):
    "传感器关机指令"
    def __init__(self):
        super().__init__("")  


cdef class CmdMotorChangeSpeed(Content):
    def __init__(self, speed):
        super().__init__("") 
        self.speed = speed


cdef class CmdMotorChangeVelocity(Content):
    def __init__(self, velocity):
        super().__init__("") 
        self.velocity = velocity


cdef class CmdMotorChangeCourse(Content):
    def __init__(self, az):
        super().__init__("") 
        self.az = az


cdef class CmdMotorChangeHeight(Content):
    def __init__(self, height):
        super().__init__("") 
        self.height = height


#--------事件---------------------------
cdef class EventHit(Content):
    def __init__(self, text=""):
        super().__init__(text) 


cdef class EventCollided(Content):
    def __init__(self, foe):
        self.foe = foe


cdef class EventNextFun(Content):
    def __init__(self, name, func, args):
        self.name = name
        self.func = func
        self.args = args
        