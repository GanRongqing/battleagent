import collections
import math

import numpy as np
import pdb
import copy
from simulation.algorithm.drive import velocity

from simulation.algorithm.shape import draw_cone

# from simulation import core
from .driver import MIN_DIS
from .. import algorithm as alg
from .. import message
from ..core.arch cimport Motor
from ..core import special_effect

distance = alg.geo.distance # 为加速，较少索引


cdef class RandomMotor(Motor):
    cpdef _move(self):
        i = np.random.randint(0, 4)
        heading = 90*i
        self.change_course(heading)
        Motor._move(self)


cdef class DurationMotor(Motor):
    """ 基于持续时间的机动组件

    在Motor的基础上增加持续时间的控制
    作为基类使用，一般不实例化
    """
    def __init__(self, unit, model):
        super().__init__(unit, model)
        self._duration = -1 # 持续时间, 单位s
        self._upper_tick = -1
        self._end_tick = -1

    cpdef _set_duration(self, float duration):
        """ 设置持续时间 """
        self._duration = duration
        self._upper_tick = self.engine.tick
        self._end_tick = self._upper_tick + duration*1000

    cpdef _clear_duration(self):
        """ 清除当前的持续时间(如果有) """
        self._duration = -1 # 持续时间, 单位s
        self._upper_tick = -1
        self._end_tick = -1


cdef class WaypointsMotor(DurationMotor):
    """ 基于航路点的机动组件 

    在Motor的基础上增加了按航路点运动功能
    作为ManeuverMotor的基类，一般不实例化
    """
    def __init__(self, unit, model):
        super().__init__(unit, model)
        self._waypoints = [] # 航路点,第0个点是下一个要机动到的点
        self._speeds = []
        self._events = [] # 抛出抵达第i个航路点的航路事件
        # 航路点对应的速度,速度的长度和航路点长度一样
        # i-1(i=0时i-1表示当前的位置点)和i航路点之间的速度为第i个速度
        self._num_waypoint = 0 #航路点数量
        self._current_waypoint_id = -1 #正在飞向的id
        self._next_waypoint_id = 0 #下一个要飞向的id

    property is_free:
        def __get__(self):
            """ 判断是否是自由状态
        
            只有自由状态下才可以直接改变速度，否则应该在按航路点运动时自动计算速度的改变量
            """
            flag = super().is_free
            if not flag:
                return False
            else:
                if self._waypoints != []:
                    return False
                else:
                    return True

    cpdef _set_waypoints(self, waypoints, list speeds=None, speed=None, list events=None):
        """ 设置航路点以及速度 """
        self._waypoints = np.array(waypoints) 
        self._next_waypoint_id = 0 
        self._num_waypoint = len(waypoints)  #　waypoints的类型为list或np.array均可以
        if speeds is not None:
            self._speeds = speeds
        elif speed is not None:
            self._speeds = [speed]*self._num_waypoint
        else:
            self._speeds = [self.speed]*self._num_waypoint
        if events is not None:
            assert len(events) == self._num_waypoint
            self._events = events

        # 解决初始点与当前位置一致或非常接近的问题
        period = self._state_period
        period = 1 if period <= 0 else period
        while self._next_waypoint_id < self._num_waypoint:
            if distance(self.coords, np.array(self._waypoints[self._next_waypoint_id,:])) < 1.2*self.speed*period: # 1.2为经验扩大系数
                if self._events:
                    content = message.event.EventManeuver(self._events[self._next_waypoint_id], self._waypoints[self._next_waypoint_id,:])
                    self._send_event(self.unit.commander, content) # 设置机动事件时必须有指挥员
                self._next_waypoint_id += 1
            else:
                break
        if self._next_waypoint_id == self._num_waypoint:
            # 由于给定的位置与当前位置非常接近，直接走完。但基于waypoints的机动指令的结束行为仍然执行
            self.engine.log_warning(f"{self.ucname}由于给定的位置与当前位置非常接近，直接走完")
            return
        velocity = alg.drive.velocity3(self._speeds[self._next_waypoint_id], self.coords, 
                    self._waypoints[self._next_waypoint_id,:]) 
        self._current_waypoint_id = self._next_waypoint_id
        self._velocity = velocity
        self.engine.log_info("TURN %d/%d %s %s %s %s", 
                        self._next_waypoint_id, self._num_waypoint, self.unit,
                        "(%0.3f,%0.3f,%0.3f)" % tuple(self._waypoints[self._next_waypoint_id,:]),
                        "Velocity", "(%0.3f,%0.3f,%0.3f)" % tuple(self.velocity))

    cpdef _clear_waypoints(self):
        """ 清除当前的航路点(如果有) """
        if self._num_waypoint > 0:
            self._waypoints = []
            self._speeds = []
            self._events = []
            self._num_waypoint = 0
            self._current_waypoint_id = -1
            self._next_waypoint_id = 0

    cpdef _move(self):
        """ 按航路点更新运动状态 """
        DurationMotor._move(self)
        if self._ref_unit: return
        if self._num_waypoint == 0:
            # 没有航路点
            return

        # if self.unit.name == "忠诚僚机_2" and self.mode == "Hover":
        #     import pdb; pdb.set_trace()

        period = self._state_period
        assert period > 0
        while self._next_waypoint_id < self._num_waypoint:
            #20240517Runke:三维坐标判断更改为二维坐标判断
            if distance(self.coords[0:2], np.array(self._waypoints[self._next_waypoint_id,0:2])) < 1.2*self.speed*period: # 1.2为经验扩大系数
                if self._events:
                    content = message.event.EventManeuver(self._events[self._next_waypoint_id], self._waypoints[self._next_waypoint_id,:])
                    self._send_event(self.unit.commander, content) # 设置机动事件时必须有指挥员
                self._next_waypoint_id += 1
            else:
                break

        if self._next_waypoint_id == self._num_waypoint: 
            # 走完航路点
            # 此处代码不能提到前面
            return

        if self._next_waypoint_id > self._current_waypoint_id:
            next_point = self._waypoints[self._next_waypoint_id,:]
            velocity = alg.drive.velocity(self._speeds[self._next_waypoint_id], self.coords, next_point)
            self._current_waypoint_id = self._next_waypoint_id
            self._velocity = velocity
            self.engine.log_info("TURN %d/%d %s %s %s %s", 
                            self._next_waypoint_id, self._num_waypoint, self,
                            "(%0.3f,%0.3f,%0.3f)" % tuple(self._waypoints[self._next_waypoint_id,:]),
                            "Velocity", "(%0.3f,%0.3f,%0.3f)" % tuple(self.velocity))

    cpdef list _draw(self, ax=None, str mode="draw"):
        items = []
        if self._waypoints != []:
            if self.engine.render_config["waypoints_units"] == "all" or self.unit.name in self.engine.render_config["waypoints_units"]:
                if mode == "draw":
                    ax.plot(self._waypoints[:,0], self._waypoints[:,1], color=self.group.lower())
                else: # symbol
                    symbol = alg.shape.Symbol(
                        mode="Line", type_="Waypoints", group=self.group, name=self.name,
                        x=self._waypoints[:,0].tolist(), y=self._waypoints[:, 1].tolist(), color=self.group)
                    items.append(symbol)
        return items

cdef class ManeuverMotor(WaypointsMotor):
    """ 基于机动指令的通用机动组件
    
    机动组件也是比较特殊的组件，其实每一类组件都有其固有的特点
    在有限状态机的基础上，进一步封装不同的机动模式(mode)，不同的mode对应不同的机动动作(函数)
    与有限状态机类型，但不是按条件转移，而是按序列依次执行
    """
    def __init__(self, unit, model):
        super().__init__(unit, model)
        self._maneuver_cmds = collections.deque()  # 机动指令序列
        self._current_maneuver_cmd = None # 当前正在执行的机动指令
        self._completed_end_cmd = False # 标记是否完成对当前指令的善后处理
        self._is_frozen = False # 是否冻结

    property mode:
        def __get__(self):
            """ 模式 
            
                当前指令中的mode，当当前指令为None时，返回None
                特殊的mode：
                    None: 无任何指令在执行， 且指令序列‘必须是’空
                    Frozen: 冻结状态
            """
            if self._is_frozen:
                return "Frozen"
            else:
                if self._current_maneuver_cmd is not None:
                    return self._current_maneuver_cmd["mode"]
                else:
                    return None

    property compound_mode:
        def __get__(self):
            """ 复合模式，最上层的 """
            return "Compound"

    property is_repeat_mode:
        def __get__(self):
            """ 判断当前motor是否处于周期性执行的状态 """
            if self._current_maneuver_cmd is not None:
                if self._current_maneuver_cmd.get("repeat", False) or self._current_maneuver_cmd.get("retrace", False):
                    return True
            return False

    property is_free:
        def __get__(self):
            """ 判断是否是自由状态
        
            只有自由状态下才可以直接改变速度，否则应该在按航路点运动时自动计算速度的改变量
            """
            flag = super().is_free
            if not flag:
                return False
            else:
                if self.mode in [None, "Frozen"]:
                    return True
                else:
                    return False

    # 定义mode的开始和结束动作
    cpdef _velocity_begin(self, cmd):
        self.change_velocity(cmd["velocity"])
        duration = cmd.get("duration", 0)
        if duration > 0:
            self._set_duration(duration)
    
    cpdef _speed_begin(self, cmd):
        self.change_speed(cmd["speed"], ignore=True)
        if "event1" in cmd:
            content = message.event.EventManeuver(cmd["event1"])
            self._send_event(self.unit.commander, content) # 设置机动事件时必须有指挥员
        duration = cmd.get("duration", 0)
        if duration > 0:
            self._set_duration(duration)

    cpdef _speed_end(self, cmd):
        if "event2" in cmd:
            content = message.event.EventManeuver(cmd["event2"])
            self._send_event(self.unit.commander, content) # 设置机动事件时必须有指挥员

    cpdef _course_begin(self, cmd):
        self.change_course(cmd["course"], ignore=True)
        duration = cmd.get("duration", 0)
        if duration > 0:
            self._set_duration(duration)

    cpdef _acce_begin(self, cmd):
        self.change_acce(cmd["acce"], ignore=True)
        duration = cmd.get("duration", 0)
        if duration > 0:
            self._set_duration(duration)

    cpdef _acce_end(self, cmd):
        self.change_acce([0, 0, 0], ignore=True)

    cpdef _turn_begin(self, cmd):
        coords = self.coords
        course = self.course
        theta = cmd["theta"] # 转弯角度
        radius = cmd["radius"] # 转弯半径
        clockwise = cmd.get("clockwise", True) # 顺时针或逆时针
        points = alg.drive.turnPointsCal(coords, course, theta, radius=radius, clockwise=clockwise)
        self._set_waypoints(points[1:]) # 去掉当前点

    cpdef _waypoints_begin(self, cmd):
        waypoints = cmd["waypoints"]
        speeds = cmd.get("speeds", None)
        speed = cmd.get("speed", None)
        events = cmd.get("events", None)
        self._set_waypoints(waypoints, speeds=speeds, speed=speed, events=events)

    cpdef _waypoints_end(self, cmd):
        # 重复指令
        repeat = cmd.get("repeat", False)
        if repeat is True and ( not self._maneuver_cmds):
            self._maneuver_cmds.appendleft(cmd)  # 继续
            return 
        if isinstance(repeat, int) and repeat > 0:
            cmd["repeat"] = repeat-1
            self._maneuver_cmds.appendleft(cmd)  # 继续
            return 
        # 折返指令
        retrace = cmd.get("retrace", False)
        if retrace is True and ( not self._maneuver_cmds):
            waypoints = cmd["waypoints"]
            cmd["waypoints"] = waypoints[::-1]
            self._maneuver_cmds.appendleft(cmd)  # 继续
            return 
        if isinstance(retrace, int) and retrace > 0:
            waypoints = cmd["waypoints"]
            cmd["waypoints"] = waypoints[::-1]
            cmd["retrace"] = retrace-1
            self._maneuver_cmds.appendleft(cmd)  # 继续
            return 

    cpdef _begin_maneuver_cmd(self):
        """ 处理机动指令，开始机动
        """
        self._completed_end_cmd = False
        cmd = self._current_maneuver_cmd
        self.engine.log_info(f"{self} Begin Handle {self.mode}")
        # 指令的开始动作必须得有
        cmd_name = cmd.get("cmd_name", None)
        if cmd_name:
            _cmd = self.engine.cmd_collections[cmd_name]
            _cmd.begin_time = self.engine.time
        getattr(self, "_"+cmd["mode"]+"_begin")(cmd)

    cpdef _end_maneuver_cmd(self, bint normal=True):
        """ 当前机动指令执行完成或强行中断后的善后处理

        normal: 是否时正常结束的
        """
        self._completed_end_cmd = True
        cmd = self._current_maneuver_cmd
        self.engine.log_info(f"{self} End Handle {self.mode}")
        if hasattr(self, "_"+cmd["mode"]+"_end"):
            # 指令的结束动作可以没有
            getattr(self, "_"+cmd["mode"]+"_end")(cmd)


        # 如果没有cmd_name，则不跟踪指令的执行情况
        cmd_name = cmd.get("cmd_name", None)
        if cmd_name is None:
            return
        # 指令如果附加了指令名称，则对指令的完成情况进行处理
        if (("repeat" in cmd) and (cmd["repeat"] == True or cmd["repeat"] > 0) or 
            ("retrace" in cmd) and (cmd["retrace"] == True or cmd["retrace"] > 0)):
            if normal:
                pass # 正常中间结束（下次仍有）的重复性或折返式指令，不对指令的结束状态进行处理
            else:
                # 被打断的重复性指令，标记为结束
                cmd_name = cmd.get("cmd_name", None)
                if cmd_name:
                    _cmd = self.engine.cmd_collections[cmd_name]
                    _cmd.end_time = self.engine.time
                    _cmd.res = "结束"
        else:
            cmd_name = cmd.get("cmd_name", None)
            if cmd_name:
                _cmd = self.engine.cmd_collections[cmd_name]
                _cmd.end_time = self.engine.time
                if normal:
                    _cmd.res = "成功"
                else:
                    _cmd.res = "失败"

    cpdef clear_current_cmd(self):
        if (self._current_maneuver_cmd is not None) and (not self._completed_end_cmd):
             # 只有还未进行善后处理的指令才对当前正在执行的机动指令的善后处理
             # 避免重复处理
             temp = copy.deepcopy(self._maneuver_cmds)
             self._end_maneuver_cmd(normal=False)
             self._maneuver_cmds = temp # 避免在善后处理时增加新的机动指令
        # 考虑到善后处理可能会增加新的机动指令(比如周期性指令)，因此下述指令放在善后处理之后
        self._clear_waypoints()
        self._clear_duration()
        self._current_maneuver_cmd = None 

    cpdef clear_cmds(self, bint is_clear_current=True):
        if is_clear_current:
            self.clear_current_cmd()#增加一个只清除命令队列的选项
        self._maneuver_cmds = collections.deque() 

    cpdef add_maneuver_cmd(self, cmd):
        """ 当mode为None时立即执行，否则加入待执行序列末尾 
        """
        if (self.mode == None) and (self._ref_unit is None) and (not self._is_frozen):
                self._current_maneuver_cmd = cmd
                self._begin_maneuver_cmd()
        else:
             self._maneuver_cmds.append(cmd)

    cpdef insert_maneuver_cmd(self, cmd, bint rightnow=False):
        """
        当mode为None时或rightnow为True时清空当前状态，立即执行
        否则， 插入到待执行序列之前
        """
        if (self.mode == None or rightnow) and (self._ref_unit is None) and (not self._is_frozen):
            self.clear_current_cmd()
            self._current_maneuver_cmd = cmd
            self._begin_maneuver_cmd()
        else:
            self._maneuver_cmds.appendleft(cmd)

    cpdef freeze(self):
        """ 冻结所有指令
        
        一旦冻结，在解冻之前，该类的任何函数都不执行，只能通过更底层的命令进行操控
        在解冻之后才能继续执行
        """
        self._is_frozen = True
        # 冻结时清空持续时间和航路点,但不清空当前指令,因为存在重复执行的指令
        self._clear_waypoints()
        self._clear_duration()

    cpdef unfreeze(self):
        """ 解冻所有指令

        解冻后需清除当前指令，并立即执行下一个指令
        之所以现在清除，而不是在冻结时清除是因为存在重复执行的指令
        而且之所以清除，是因为指令都是按航迹点运动的，不清除无意义
        """
        self._is_frozen = False
        self.clear_current_cmd()
        if self._maneuver_cmds:
            cmd = self._maneuver_cmds.popleft()
            self._current_maneuver_cmd = cmd
            self._begin_maneuver_cmd()

    cpdef _move(self):
        WaypointsMotor._move(self)
        if self._ref_unit: return
        if self._is_frozen: return # 冻结指令则什么也不做
        cdef bint flag = False # 是否完成当前指令
        if self._num_waypoint > 0  and self._next_waypoint_id == self._num_waypoint:
            # 走完航路点
            flag = True
            self._clear_waypoints()
        elif self._end_tick > 0 and self.engine.tick >= self._end_tick:
            # 走完持续时间
            flag = True
            self._clear_duration()
        if flag:
            # 完成当前指令且当前指令不为空则
            if self._current_maneuver_cmd is not None:
                former_cmd = self._current_maneuver_cmd
                self._end_maneuver_cmd() # 对当前正在执行的机动指令的善后处理,该处理不能改变当前指令
                assert former_cmd == self._current_maneuver_cmd, "former:%s, current:%s" % (former_cmd, self._current_maneuver_cmd)
                #防止结束执行过程中指令已经切换，导致新的指令消失，一般来说不会，除非强制打断了当前指令或者调用了
                self._current_maneuver_cmd = None

        if self._num_waypoint == 0 and self._end_tick == -1:
            # 新的开始
            if self._maneuver_cmds:
                cmd = self._maneuver_cmds.popleft()
                self._current_maneuver_cmd = cmd
                self._begin_maneuver_cmd()

    cpdef _oval_begin(self,cmd):
        '''
            生成椭圆上的点列表

            Args:
                cmd(str):指令字符串
        '''
        clockwise = cmd.get("clockwise", True)  # 顺时针或逆时针
        center = cmd.get("center", None)  # center(tuple[float,float,float]): 中心点位置坐标(x,y,h)
        az = cmd.get("az", None)  # az(tuple[float,float,int]): 区域长,宽，角度
        points = alg.drive.oval_cal(center=center,az=az, clockwise=clockwise)
        self._set_waypoints(points)  # 去掉当前点

    cpdef _oval_end(self,cmd):
        # 重复指令
        repeat = cmd.get("repeat", False)
        if repeat is True and ( not self._maneuver_cmds):
            self._maneuver_cmds.appendleft(cmd)  # 继续
            return 
        if isinstance(repeat, int) and repeat > 0:
            cmd["repeat"] = repeat-1
            self._maneuver_cmds.appendleft(cmd)  # 继续
            return 

    cpdef _lineCircle_begin(self,cmd):
        '''
            生成直线上的点列表

            Args:
                cmd(str):指令字符串
        '''
        coords = cmd.get("coords", True)  # 起始点
        dis = cmd.get("dis", None)  # 运动距离（m）
        speed = cmd.get("speed", None)  # 运动速度（m）
        period = cmd.get("period", None)  # 运动周期
        flag = -1 if dis < 0 else 1
        num = math.ceil(abs(dis) / (speed*period))
        points = []
        for i in range(num):
            y = coords[1] + speed * period * i * flag
            points.append([coords[0],y,coords[2]])
        points_ = points.copy()
        points.reverse()

        points_.extend(points)
        self._set_waypoints(points)

    cpdef _lineCircle_end(self,cmd):
        repeat = cmd.get("repeat", False)
        if repeat is True and ( not self._maneuver_cmds):
            self._maneuver_cmds.appendleft(cmd)  # 继续
            return 
        if isinstance(repeat, int) and repeat > 0:
            cmd["repeat"] = repeat-1
            self._maneuver_cmds.appendleft(cmd)  # 继续
            return 

    cpdef _rectangularCircle_begin(self,cmd):
        '''
            生成矩形上的点列表

            Args:
                cmd(str):指令字符串
        '''
        coords = cmd.get("coords", True)  # 起始点
        length = cmd.get("length", None)  # 长度m）
        width = cmd.get("width", None)  # 宽度（m）
        speed = cmd.get("speed", None)  # 运动速度（m）
        period = cmd.get("period", None)  # 运动周期
        points = alg.drive.rectangular_circle_cal(width,length,speed,period,coords)
        self._set_waypoints(points[1:])  # 去掉当前点,否则导致计算速度时，speed 为0

    cpdef _rectangularCircle_end(self,cmd):
        repeat = cmd.get("repeat", False)
        if repeat is True and ( not self._maneuver_cmds):
            self._maneuver_cmds.appendleft(cmd)  # 继续
            return 
        if isinstance(repeat, int) and repeat > 0:
            cmd["repeat"] = repeat-1
            self._maneuver_cmds.appendleft(cmd)  # 继续
            return 

cdef class _PlaneMotor(ManeuverMotor):
    """ 飞机机动组件，作为固定翼和旋转翼飞机机动组件的基类
    """
    def __init__(self, unit, model):
        super().__init__(unit, model)
        self._send_rtb = False

    # def get_current_mode(self):
    #     if self._current_maneuver_cmd is not None:
    #         return self._current_maneuver_cmd["mode"]
    #     return None

    cpdef get_next_mode(self):
        if not self._maneuver_cmds:
            return None
        else:
            return self._maneuver_cmds[0]["mode"]

    cpdef _Climb_begin(self, cmd):
        # 爬升指令
        climb_point = self.coords
        climb_az = self.course
        climb_dis = self.attr["climb_dis"] # 起飞阶段爬升的水平距离
        climb_height = self.attr["climb_height"] # 起飞阶段爬升的垂直距离
        points = alg.trajectory.plane_climb_points(climb_point, climb_az, climb_dis, climb_height)
        self._set_waypoints(points[1:,:].tolist())

    cpdef _Climb_end(self, cmd):
        # 爬升指令
        # import pdb; pdb.set_trace()
        if not self._maneuver_cmds:
            # 如果后续没有机动指令
            self._maneuver_cmds.append({"mode":"Hover", "repeat":True}) 
            # self._begin_maneuver_cmd({"mode":"Hover", "repeat":True})

    cpdef _Turn_begin(self, cmd):
        # 转弯指令
        coords = self.coords
        course = self.course
        radius = max(self.attr["turn_radius"], cmd.get("turn_radius", 0)) # 转弯半径
        theta = cmd["theta"] # 转弯角度
        clockwise = cmd.get("clockwise", True) # 顺时针或逆时针
        points = alg.drive.turnPointsCal(coords, course, theta, radius=radius, clockwise=clockwise)
        self._set_waypoints(points[1:]) # 去掉当前点

    cpdef _FlyOnCourse_begin(self, cmd):
        # 按航线飞行
        waypoints = cmd["waypoints"]
        speeds = cmd.get("speeds", None)
        speed = cmd.get("speed", None)
        events = cmd.get("events", None)
        self._set_waypoints(waypoints, speeds=speeds, speed=speed, events=events)
        # import pdb; pdb.set_trace()

    cpdef _FlyOnCourse_end(self, cmd):
        # 按航线飞行
        # 重复指令
        repeat = cmd.get("repeat", False)
        if repeat is True and ( not self._maneuver_cmds):
            self._maneuver_cmds.appendleft(cmd)  # 重复执行，闭合曲线
            return 
        if isinstance(repeat, int) and repeat > 0:
            cmd["repeat"] = repeat-1
            self._maneuver_cmds.appendleft(cmd)  # 重复执行，闭合曲线
            return 
        # 折返指令
        retrace = cmd.get("retrace", False)
        if retrace is True and ( not self._maneuver_cmds):
            waypoints = cmd["waypoints"]
            cmd["waypoints"] = waypoints[::-1]
            self._maneuver_cmds.appendleft(cmd)  # 继续
            return 
        if isinstance(retrace, int) and retrace > 0:
            waypoints = cmd["waypoints"]
            cmd["waypoints"] = waypoints[::-1]
            cmd["retrace"] = retrace-1
            self._maneuver_cmds.appendleft(cmd)  # 继续
            return 

    cpdef _ReturnToBase_begin(self, cmd):
        # 返回基地
        aim_coords = self.unit.home_unit.coords.copy()
        aim_coords[2] = self.coords[2]
        speeds = cmd.get("speeds", None)
        speed = cmd.get("speed", None)
        if self.speed == 0:
            speed = 300
        self._set_waypoints([aim_coords], speeds=speeds, speed=speed)

    cpdef _ReturnToBase_end(self, cmd):
        # 返回基地
        if alg.geo.distance(self.coords[0:2], self.unit.home_unit.coords[0:2]) <= 1000:
            event = message.event.EventReturnToBase("End")
            self._send_event(self.unit.driver, event)
        else:
            self._maneuver_cmds.appendleft(cmd)

    cpdef _Decline_begin(self, cmd):
        # 下降
        pass
    
    cpdef _Advance_begin(self, cmd):
        advance_speed = cmd["speed"]
        advance_time = cmd["duration"]
        az_rad = np.deg2rad(self.course)
        vx = advance_speed * np.sin(az_rad)
        vy = advance_speed * np.cos(az_rad)
        self._velocity = np.array([vx, vy, 0])
        self._set_duration(advance_time)
    
    cpdef _Advance_end(self, cmd):
        pass

    # 暂时不判断航程是否超过
    # def _move(self):
    #     super()._move()
    #     if self._ref_unit: return
    #     if self.distance > 0.5 * self.attr.dmax and (not self._send_rtb):
    #         # 航程不足，需返回基地事件
    #         # import pdb; pdb.set_trace()
    #         if self.unit.home_unit:
    #             self._send_rtb = True
    #             event = message.event.EventReturnToBase("Begin")
    #             self._send_event(self.unit.driver, event)


cdef class FixedWingMotor(_PlaneMotor):
    cpdef _TakeOff_begin(self, cmd):
        # 起飞指令
        # tf_dis = self.attr["tf_dis"] # 起飞阶段滑行距离
        tf_time = self.attr["tf_time"] # 起飞时间
        tf_speed = self.attr["speed"] # 起飞速度默认为与正常飞行速度一致
        az_rad = np.deg2rad(self.course)
        vx = tf_speed*np.sin(az_rad)
        vy = tf_speed*np.cos(az_rad)
        self._velocity = np.array([-vx, -vy, 0])
        if self.speed > 0:
            self._velocity = np.array([-vx, -vy, 0]) # 逆向起飞
        else:
            self._velocity = np.array([vx, vy, 0]) # 陆上固定机场
        # dst_point =  self._coords + self._velocity*tf_time
        # self._set_waypoints([dst_point])
        self._set_duration(tf_time)

    cpdef _TakeOff_end(self, cmd):
        # 起飞指令
        prob = self.attr["tf_failure_prob"]
        if np.random.random() < prob:
            flag = "Failure"
        else:
            flag = "Success"   
        # 发送起飞消息
        event = message.event.EventTakeOff(self.unit, flag)
        self._send_event(self.unit, event)
        if flag == "Success":
            self._maneuver_cmds.appendleft({"mode":"Climb"}) 
            # self._begin_maneuver_cmd({"mode":"Climb"}) 

    cpdef _LandOn_begin(self, cmd):
        # 开始着陆
        print(self.engine.tick,f"{self.unit.name} 开始在{self.unit.home_unit.name}着陆")
        aim_coords = self.unit.home_unit.coords.copy()
        aim_coords[2] = 500
        if self.speed == 0:
            self._set_waypoints([aim_coords], speeds = None, speed = 300)
        else:
            self._set_waypoints([aim_coords])

    cpdef _LandOn_end(self, cmd):
        # 着陆
        print(self.engine.tick,f"{self.unit.name} 完成在{self.unit.home_unit.name}着陆")
        prob = self.attr["lo_failure_prob"]
        if np.random.random() < prob:
            flag = "Failure"
        else:
            flag = "Success" 
        event = message.event.EventLandOn(self.unit, flag)
        self._send_event(self.unit, event)
        
    cpdef _Hover_begin(self, cmd):
        # 盘旋指令
        coords = self.coords
        course = self.course
        clockwise = cmd.get("clockwise", True) # 顺时针或逆时针
        style = cmd.get("style", "O")
        if style == "O":
            theta = 360 # 盘旋角度
            radius = cmd.get("hover_radius", self.attr["hover_radius"]) # 盘旋半径
            points = alg.drive.turnPointsCal(coords, course, theta, radius=radius, clockwise=clockwise)
        elif style == "8":
            theta = 360 # 盘旋角度
            radius = cmd.get("hover_radius", self.attr["hover_radius"]) # 盘旋半径
            az = cmd["az"]
            points = alg.drive.path8PointsCal(coords, course, az, radius=radius, clockwise=clockwise)
        elif style == "0":
            # 跑道形
            az = cmd["az"]
            length = cmd["length"]
            width = cmd["width"]
            init_dis = cmd.get("init_dis", None)
            points = alg.drive.path0PointsCal(coords, course, az, length, width, clockwise=clockwise, init_dis=init_dis)
        self._set_waypoints(points[1:]) # 去掉当前点

    cpdef _Hover_end(self, cmd):
        # 重复盘旋指令
        repeat = cmd.get("repeat", True) # 默认Hover的repeat为True
        if repeat is True and ( not self._maneuver_cmds):
            self._maneuver_cmds.appendleft(cmd)  # 继续
            return 
        if isinstance(repeat, int) and repeat > 0:
            cmd["repeat"] = repeat-1
            self._maneuver_cmds.appendleft(cmd)  # 继续
            return         


cdef class RotaryWingMotor(_PlaneMotor):
    cpdef _TakeOff_begin(self, cmd):
        # 起飞指令 
        tf_speed = self.attr["tf_speed"] # 起飞速度默认为与正常飞行速度一致
        assert tf_speed > 0
        tf_height = self.attr["tf_height"] # 起飞高度
        tf_time = tf_height / tf_speed
        self._velocity = np.array([0, 0, tf_speed], dtype=np.float64)
        self._set_duration(tf_time)

    cpdef _TakeOff_end(self, cmd):
        # 起飞指令
        prob = self.attr["tf_failure_prob"]
        if np.random.random() < prob:
            flag = "Failure"
        else:
            flag = "Success"   
        # 发送起飞消息
        event = message.event.EventTakeOff(self.unit, flag)
        self._send_event(self.unit, event)
        if flag == "Success":
            self._velocity =  np.array([0, 0, 0], dtype=np.float64)

    cpdef _LandOn_begin(self, cmd):
        # 开始着陆
        print(self.engine.tick,f"{self.unit.name} 开始在{self.unit.home_unit.name}着陆")
        aim_coords = self.unit.home_unit.coords.copy()
        aim_coords[2] = 500
        if self.speed == 0:
            self._set_waypoints([aim_coords], speeds=None, speed=300)
        else:
            self._set_waypoints([aim_coords])

    cpdef _LandOn_end(self, cmd):
        # 着陆
        print(self.engine.tick,f"{self.unit.name} 完成在{self.unit.home_unit.name}着陆")
        prob = self.attr["lo_failure_prob"]
        if np.random.random() < prob:
            flag = "Failure"
        else:
            flag = "Success" 
        event = message.event.EventLandOn(self.unit, flag)
        self._send_event(self.unit, event)
        
    cpdef _Hover_begin(self, cmd):
        # 盘旋指令
        print(f"Rotary Plane {self.unit.name} Begin Hover, speed is changed to 0 !!!")
        self.change_speed(0, ignore = True)
        duration = cmd.get("duration", 0)
        if duration > 0:
            self._set_duration(duration)


cdef class ShipMotor(ManeuverMotor):
    def __init__(self, unit, model):
        super().__init__(unit, model)
        self.is_back = False

    
    cpdef _Advance_begin(self, cmd):
        # 前进指令　　　　
        advance_time = self.attr["advance_time"]  # 前进时间
        advance_speed = self.attr["speed"]  # 前进速度默认为与正常航行速度一致
        az_rad = np.deg2rad(self.course)
        vx = advance_speed * np.sin(az_rad)
        vy = advance_speed * np.cos(az_rad)
        self._velocity = np.array([vx, vy, 0])
        self._set_duration(advance_time)
    
    cpdef _Advance_end(self, cmd):
        pass
    
    cpdef _Back_begin(self, cmd):
        # 倒退指令
        reverse_time = self.attr["reverse_time"]  # 倒退时间
        reverse_speed = self.attr["reverse_speed"]  # 倒退速度默认与正常前行速度一致
        az_rad = np.deg2rad(self.course)
        vx = reverse_speed * np.sin(az_rad)
        vy = reverse_speed * np.cos(az_rad)
        self._velocity = np.array([-vx, -vy, 0])
        self.is_back = True
        self._set_duration(reverse_time)

    cpdef _Back_end(self, cmd):
        self.is_back = False

    cpdef _Turn_begin(self, cmd):
        # 转弯指令
        coords = self.coords
        course = self.course
        radius = max(self.attr["turn_radius"], cmd.get("turn_radius", 0))  # 转弯半径
        theta = cmd["theta"]  # 转弯角度
        clockwise = cmd.get("clockwise", True)  # 顺时针或逆时针
        points = alg.drive.turnPointsCal(coords, course, theta, radius=radius, clockwise=clockwise)
        self._set_waypoints(points[1:])  # 去掉当前点
    
    cpdef _Turn_end(self, cmd):
        # 转弯指令
        repeat = cmd.get("repeat", False)
        if not self._maneuver_cmds:
            # 继续转弯
            self._maneuver_cmds.appendleft(cmd) # 继续绕圈

    cpdef _SailOnCourse_begin(self, cmd):
        # 按航线航行
        waypoints = cmd["waypoints"]
        speeds = cmd.get("speeds", None)
        speed = cmd.get("speed", None)
        self._set_waypoints(waypoints, speeds=speeds, speed=speed)

    cpdef _SailOnCourse_end(self, cmd):
        # 按航线航行
        turn_back = cmd.get("turn_back", True)
        if turn_back:
            cmd["waypoints"] = cmd["waypoints"][::-1] # 按航线折返
            cmd["turn_back"] = False
            self._maneuver_cmds.appendleft(cmd)

cdef class SubmarineMotor(ManeuverMotor):
    ''' 潜艇机动组件
    '''
    def __init__(self, unit, model):
        super().__init__(unit, model)
    
    cpdef _Rise_begin(self, cmd):
        # 上浮指令
        self._rise_last_velocity = self._velocity.copy()
        self._rise_last_velocity_norm = self._rise_last_velocity[:2] / np.sum(self._rise_last_velocity[:2]) * 0.01
        depth = self.coords[2]
        dest_depth = cmd['dest_depth']
        rise_speed = cmd['speed']
        cmd_name = cmd.get('cmd_name')
        cmd_data = self.engine.cmd_collections[cmd_name]
        if depth == 0 or dest_depth < depth or rise_speed <= 0:
            cmd_data.res = '失败'     
            return
        rise_time = (dest_depth - depth) / rise_speed
        self._velocity = np.array([self._rise_last_velocity_norm[0], self._rise_last_velocity_norm[1], rise_speed], dtype=np.float64)
        self._set_duration(rise_time)
        special_effect.SubmarineRiseStartActionEffect.gen(self.engine, self.unit.name)


    cpdef _Rise_end(self, cmd):
        self.change_velocity(self._rise_last_velocity, ignore=True)
        special_effect.SubmarineRiseEndActionEffect.gen(self.engine, self.unit.name)
        
    cpdef _Dive_begin(self, cmd):
        # 下潜指令
        self._dive_last_velocity = self._velocity.copy()
        self._dive_last_velocity_norm = self._dive_last_velocity[:2] / np.sum(self._dive_last_velocity[:2]) * 0.01
        cdef float depth = self.coords[2]
        dest_depth = cmd['dest_depth']
        dive_speed = cmd['speed']
        cmd_name = cmd.get('cmd_name')
        cmd_data = self.engine.cmd_collections[cmd_name]
        if depth > 0 or dest_depth > depth or dive_speed >= 0:
            cmd_data.res = '失败'   
            return  
        cdef float dive_time = (dest_depth - depth) / dive_speed
        self._velocity = np.array([self._dive_last_velocity_norm[0], self._dive_last_velocity_norm[1], dive_speed], dtype=np.float64)
        self._set_duration(dive_time)
        special_effect.SubmarineDiveStartActionEffect.gen(self.engine, self.unit.name)

    cpdef _Dive_end(self, cmd):
        self.change_velocity(self._dive_last_velocity, ignore=True)
        special_effect.SubmarineDiveEndActionEffect.gen(self.engine, self.unit.name)

    cpdef _Advance_begin(self, cmd):
        advance_speed = cmd["speed"]
        advance_time = cmd["duration"]
        az_rad = np.deg2rad(self.course)
        vx = advance_speed * np.sin(az_rad)
        vy = advance_speed * np.cos(az_rad)
        self._velocity = np.array([vx, vy, 0])
        self._set_duration(advance_time)
    
    cpdef _Advance_end(self, cmd):
        pass

    cpdef _Back_begin(self, cmd):
        reverse_time = cmd["speed"]  # 倒退时间
        reverse_speed = self.attr["duration"]  # 倒退速度默认与正常前行速度一致
        az_rad = np.deg2rad(self.course)
        vx = reverse_speed * np.sin(az_rad)
        vy = reverse_speed * np.cos(az_rad)
        self._velocity = np.array([-vx, -vy, 0])
        self.is_back = True
        self._set_duration(reverse_time)

    cpdef _Back_end(self, cmd):
        self.is_back = False

    cpdef _Turn_begin(self, cmd):
        # 转弯指令
        coords = self.coords
        course = self.course
        radius = max(self.attr["turn_radius"], cmd.get("turn_radius", 0)) # 转弯半径
        theta = cmd["theta"] # 转弯角度
        clockwise = cmd.get("clockwise", True) # 顺时针或逆时针
        points = alg.drive.turnPointsCal(coords, course, theta, radius=radius, clockwise=clockwise)
        self._set_waypoints(points[1:]) # 去掉当前点
    
    cpdef _Turn_end(self, cmd):
        pass

    cpdef _SailOnCourse_begin(self, cmd):
        waypoints = cmd["waypoints"]
        speeds = cmd.get("speeds", None)
        speed = cmd.get("speed", None)
        events = cmd.get("events", None)
        self._set_waypoints(waypoints, speeds=speeds, speed=speed, events=events)
    
    cpdef _SailOnCourse_end(self, cmd):
        # 重复指令
        repeat = cmd.get("repeat", False)
        if repeat is True and ( not self._maneuver_cmds):
            self._maneuver_cmds.appendleft(cmd)  # 继续
            return 
        if isinstance(repeat, int) and repeat > 0:
            cmd["repeat"] = repeat-1
            self._maneuver_cmds.appendleft(cmd)  # 继续
            return 
        # 折返指令
        retrace = cmd.get("retrace", False)
        if retrace is True and ( not self._maneuver_cmds):
            waypoints = cmd["waypoints"]
            cmd["waypoints"] = waypoints[::-1]
            self._maneuver_cmds.appendleft(cmd)  # 继续
            return
        if isinstance(retrace, int) and retrace > 0:
            waypoints = cmd["waypoints"]
            cmd["waypoints"] = waypoints[::-1]
            cmd["retrace"] = retrace-1
            self._maneuver_cmds.appendleft(cmd)  # 继续
            return