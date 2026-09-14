import collections 
from simulation.core cimport base # base cimport Node
from simulation.core cimport message # cimport HEAD, FUNC, MESSAGE, STATE

cdef class Entity(base.Node):
    """实体
    """
    def __init__(self, parent):
        super().__init__(parent)
        self._isactive = False

    property isactive:
        def __get__(self):
            return self._isactive

    ####通用接口#####
    cpdef assemble(self):
        """ 配置实体属性参数等
        """
        pass
    cpdef implement(self):
        """ 实体状态、消息处理组装等
        """
        pass
    cpdef check(self):
        """ 运行前检查等
        """
        pass
    cpdef start(self):
        """ 激活实体
        """
        self._isactive = True
    cpdef kill(self):
        """ 杀掉实体 """
        self._isactive = False

    cpdef activate(self):
        """ 组装、检查、激活实体
        """
        self.assemble()
        self.implement()
        self.check()
        self.start()

    ####可视化接口#####
    cpdef draw(self, ax):
        pass
    cpdef drawXz(self, ax):
        pass
    cpdef draw3D(self, ax):
        pass
    cpdef list drawSymbol(self):
        return []
    cpdef list drawSymbol3D(self):
        return []


cdef class Router(Entity):
    """消息转发机制基类
    """ 
    def __init__(self, parent, engine):
        super().__init__(parent)
        self.engine = engine
        self._message_handlers = {} #储存不同类型消息的处理函数
        # 添加反馈消息的处理函数
        # self._add_handler(core.message.EchoMsgBody, self._echoMsg_handler)

    cpdef message_handle(self, message.MESSAGE msg):
        """ 处理消息

        消息包括消息头、消息体以及消息内容
        此处根据消息体的类型调用不同的处理方法
        其子类会重写该方法
        """
        if not self.isactive:
            self.engine.log_debug("Inactive %s cannot handle message %s" % (self, msg))
            return
        mcls = msg.body.__class__.__name__
        if mcls not in self._message_handlers:
            raise RuntimeError("Cannot handle message: %s %s" % (self, msg))
        self.engine.log_debug("MessageHandle %s handle message[%s]", self, mcls)
        self._message_handlers[mcls](msg.body)

    cpdef _add_handler(self, mcls, handler):
        """ Add massage handler.

        其子类会重写该方法
        Args:
            mcls: messgae body class. see message.py
            handler:a function to handle the message
        """
        self._message_handlers[mcls] = handler

    cpdef _notify(self, recv, body, delay=None, delay_ms=None):
        """ 消息传递接口

        因在arch.py中会进一步封装为_send_msg/_send_cmd/_send_event/_send_task等接口
        因此在此处采用私有形式(双下划线)，后续只用封装后的，不再直接使用notify
        """
        if delay is not None and delay_ms is not None:
            raise RuntimeError("only delay or delay_ms")
        if delay is None and delay_ms is None:
            raise RuntimeError("only delay or delay_ms")
        if delay is None:
            assert delay_ms >= 0, "negative delay_ms time"
            assert isinstance(delay_ms, int)
        else:
            assert delay >= 0, "negative delay time"
            delay_ms = int(delay * 1000)
            if delay > 0 and delay_ms == 0:
                raise RuntimeError("delay:{} should > 0.001".format(delay))

        assert self is not recv, "消息不能发送给自身, 如果确实需要该功能,可通过_next实现"

        head = message.HEAD(self, recv, self.engine.tick)
        msg = message.MESSAGE(head, body)
        
        if delay_ms == 0:
            #如果时延为0，则瞬时传输，并且立即处理
            recv.message_handle(msg)
        else:
            when = self.engine.tick + delay_ms
            self.engine._cron.push(when, msg)
            self.engine.log_debug("MessageDispatch %s will handle message[%s] when: %s",
                self, msg.body.content.__class__.__name__, when)

    cpdef _next(self, func, args=None, delay=None, delay_ms=None):
        '''通过消息机制支撑函数的延时执行.
       
        函数func延迟delay或delay_ms时间再执行，args为函数的参数
        '''
        if delay is not None and delay_ms is not None:
            raise RuntimeError("only delay or delay_ms")
        if delay is None and delay_ms is None:
            raise RuntimeError("only delay or delay_ms")
        if delay is None:
            assert delay_ms >= 0, "negative delay_ms time"
            assert isinstance(delay_ms, int)
        else:
            assert delay >= 0, "negative delay time"
            delay_ms = int(delay * 1000)
        if delay_ms == 0:
            # raise RuntimeError("delay:{} should > 0".format(delay))
            # 如果时延为0，则瞬时立即处理
            if args is None:
                func()
            else:
                func(*args)
        else:
            head = message.HEAD(self, self, self.engine.tick)
            body = message.FUNC(func, args)
            msg = message.MESSAGE(head, body)
            when = self.engine.tick + delay_ms
            self.engine._cron.push(when, msg)
            self.engine.log_debug("FuncDispatch %s will exec func[%s] when: %s",
                self, msg.body.func.__name__, when)

def lambda_None():
    return None

cdef class FSM(Router):
    """有限状态机基类
    """
    def __init__(self, parent, engine):
        super().__init__(parent, engine)
        self._state = "UNIFINED"
        self._history_state = [(self.engine.tick, "UNIFINED")] #状态变换记录
        self._begin_time = self.engine.tick
        self._state_update_count = 0
        self._state_action = {"UNIFINED": [lambda: None, 0]}       
        # "UNIFINED",未初始化的状态；"DISABLE"：死亡状态       
        self._trans = collections.defaultdict(list)
        self._dispatch(self.engine.tick)

    property state:
        def __get__(self):
            return self._state

    property state_time:
        def __get__(self):
            return (self.engine.tick - self._begin_time) / 1000.0

    property _state_period_ms:
        def __get__(self):
            return self._state_action[self._state][1]

    property _state_period:
        def __get__(self):
            return self._state_action[self._state][1] / 1000.0


    cpdef state_update(self):
        """ 状态更新
        包括状态动作执行和状态跳转
        只能由Engine调用
        """
        if not self.isactive:
            self.engine.log_debug("Disabled %s will not update state", self)
            return

        work = self._state_action[self._state][0]
        self.engine.log_debug("StateUpdate %s update state[%s](%s)", self, self._state, work.__name__)
        old_state = self._state
        work()
        self._state_update_count += 1
        # 如果在执行状态动作时状态发生了变化，也即在状态动作中使用了self._change_state函数(或包含该函数的函数)
        # 则直接跳出，后续按新状态执行
        if self._state != old_state:
            if self._state != 'DEAD':
                self.engine.log_warning("%s的状态在执行[%s]状态动作时变为了[%s], 建议尽量避免该种情况", self, old_state, self._state)
            return
            
        if not self.isactive:
            self.engine.log_debug("%s的状态为[Disabled],不再转移状态", self)
            return

        for new_state, condition in self._trans[self._state]:
            ret = condition()
            assert isinstance(ret, bool), "{0}() returns {1}".format(condition.__name__, type(ret))
            if ret:
                self._change_state(new_state)
                break
        else:
            repeat_ms = self._state_action[self._state][1]
            if repeat_ms > 0:
                when = self.engine.tick + repeat_ms
                self._dispatch(when)
            else:
                self.engine.log_debug("%s will not transfer state, end at state[%s]", self, self._state)

    cpdef _change_state(self, str new_state):
        if not self.isactive:
            self.engine.log_warning("Inactive %s cannot change state to %s " % (self, new_state))
            return 
        assert new_state in self._state_action, "%s newstate %s is not in %s" % (self, new_state, self._state_action)
        self.engine.log_info("StateJump %s==>%s", self, new_state)
        self._state = new_state
        self._history_state.append((self.engine.tick, new_state))
        self._begin_time = self.engine.tick
        self._state_update_count = 0
        # 跳转到新状态的更新策略
        repeat_ms = self._state_action[new_state][1]
        right_now = self._state_action[new_state][2]
        init = self._state_action[new_state][3]
        init() # 无论如何立即执行状态的初始化动作
        if repeat_ms == 0 or right_now:
            self.state_update()
        else:
            when = self.engine.tick + repeat_ms
            self._dispatch(when)
       
    cpdef _dispatch(self, double when):
        head = message.HEAD(self, self, self.engine.tick)
        body = message.STATE(self._state)
        msg = message.MESSAGE(head, body)
        self.engine._cron.push(when, msg)
        if self._state != "UNIFINED":
            self.engine.log_debug("StateDispatch %s will update state[%s] when: %s", self, self._state, when)

    def _add_state(self, state, work, repeat=None, repeat_ms=None, right_now=True, init=lambda: None):
        """ Add state, state action and repeat period.

        Args:
            state: 状态,str
            work: 状态对应的动作, 函数
            repeat: 单位: s 
                repeat = 0: 立即执行,但只执行一次
                repeat > 0: 根据right_now决定是否立即执行，并每隔repeat周期执行
            repeat_ms: 与repeat作用一致，但单位是ms(毫秒)
            right_now: 是否立即执行
            init: 状态对应的初始化动作
        """
        if repeat is not None and repeat_ms is not None:
            raise RuntimeError("only repeat or repeat_ms")
        if repeat is None and repeat_ms is None:
            raise RuntimeError("only repeat or repeat_ms")
        if repeat is None:
            assert repeat_ms >= 0, "negative repeat_ms time"
            assert isinstance(repeat_ms, int)
        else:
            assert repeat >= 0, "negative repeat time"
            repeat_ms = int(repeat * 1000)
            if repeat > 0 and repeat_ms == 0:
                raise RuntimeError("repeat:{} should >= 0.001".format(repeat)) 
        if repeat_ms == 0:
            assert right_now # 只有周期大于0时才可以将right_now设置为False
        self._state_action[state] =[work, repeat_ms, right_now, init]

    cpdef _add_transfer(self, str state, str new_state, condition):
        #状态变化与变化规则写入顺序有关
        """ Add transfer condition.

        If condition function [condition] returns True, 
        Args:
            state:a string the initial state of transfer 
            new_state:a string the target state of transfer
            condition:a function if it return true transfer be done
        """
        assert new_state != state
        self._trans[state].append((new_state, condition))

    cpdef implement(self):
        """ 添加状态或消息处理
        """
        pass

    cpdef start(self):
        """ 激活实体
        """
        # super().start()
        Router.start(self)
        try:
            assert self._history_state[0][0] == self.engine.tick, "生成后必须在同一时刻激活， 否则会一直停留在UNDEFINED状态"
        except:
            print("生成后必须在同一时刻激活， 否则会一直停留在UNDEFINED状态")