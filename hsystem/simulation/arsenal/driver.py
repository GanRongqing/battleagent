from cmath import inf
import collections
import pdb
from turtle import right

import numpy as np

from simulation.algorithm.drive import velocity

from .. import algorithm as alg
from .. import arsenal as asn
from .. import core, message


MIN_DIS = 100  # 判断是否到达指定点的最小距离约束，只要小于该距离，则认为到达指定点


class NormalDriver(core.arch.Driver):
    def __init__(self, unit, model):
        super().__init__(unit, model)
        self._motor = self.unit.motor
        self._cplan = None  # 位置计划
        self._splan = None  # 标量速度计划, 可与位置计划相容
        self._tcplan = None  # 时间、位置计划
        self._simple_plan = None  # 简单一次性机动指令
        self._quaternions = collections.deque()  # 时间、位置四元数序列
        self._points = collections.deque()  # 位置序列
        self._is_adjust_course = True  # cplan和splan使用
        self._repeat_times = None  # cplan使用
        self._upper_tick = None  # cplan和splan使用
        self._end_tick = None  # splan和simple_plan使用
        self._move_plans = collections.deque()  # 机动计划序列

    def set_move_plan(self, cplan=None, splan=None, tcplan=None, simple_plan=None, mode="clear"):
        """ 受领或设置航行计划任务并着手计算并下发

        Args:
            cplan: 三维位置计划,dict
            splan: 标量速度计划,dict
            tcplan: 时间、位置计划,list
            simple_plan: 简单一次性机动指令，如改变速度、改变航向等,dict
            mode: 模式
                append: 追加模式，追加到机动计划序列之后
                clear: 立即模式，清空当前机动计划序列，并立即执行
        """
        assert cplan or splan or tcplan or simple_plan, "必有一个非空"
        assert not ((cplan or splan) and tcplan and simple_plan), "不能同时非空"
        if mode == "clear":
            self._cplan = None
            self._splan = None
            self._tcplan = None
            self._simple_plan = None
            self._move_plans.append([cplan, splan, tcplan, simple_plan])
            self._work()  # 立即工作
        else:
            self._move_plans.append([cplan, splan, tcplan, simple_plan])

    def _handle_move_plan(self, cplan, splan, tcplan, simple_plan):
        self._cplan = cplan
        self._splan = splan
        self._tcplan = tcplan
        self._simple_plan = simple_plan
        self._upper_tick = self.engine.tick
        if simple_plan:
            if "duration" in simple_plan:
                self._end_tick = self.engine.tick + \
                    simple_plan["duration"]*1000
            else:
                self._end_tick = self.engine.tick  # 不持续
            self._handle_simple_plan()
        if cplan:
            self._is_adjust_course = True
            self._handle_cplan()
        if splan:
            if "duration" in splan:
                self._end_tick = self.engine.tick + splan["duration"]*1000
            else:
                self._end_tick = np.inf
        if tcplan:
            self._quaternions = collections.deque()
            self._quaternions.extend(tcplan.copy())

    def _handle_simple_plan(self):
        """ 简单的一次性机动指令
        """
        if self._simple_plan['mode'] == 'velocity':
            self._motor.change_velocity(
                np.array(self._simple_plan['velocity']))
        elif self._simple_plan['mode'] == 'speed':
            self._motor.change_speed(self._simple_plan['speed'])
        elif self._simple_plan['mode'] == 'course':
            self._motor.change_course(self._simple_plan['course'])
        elif self._simple_plan['mode'] == 'acce':
            self._motor.change_acce(np.array(self._simple_plan['acce']))
        else:
            raise RuntimeError("unkown simple plan %s" % self._cplan['mode'])

    def _handle_cplan(self):
        """  根据航行计划任务生成速度和时刻数组
        """
        self._points = collections.deque()
        points = []
        if self._cplan['mode'] == 'round':  # 环绕
            self._repeat_times = self._cplan.get('repeat', np.inf)  # 重复次数
            coords = self.coords
            course = self.course
            theta = 360
            if "center" in self._cplan:
                assert len(self._cplan['center']) == 3, "长度须为3"
                center = np.array(self._cplan['center'])
                radius = alg.geo.distance(coords, center)
                self._cplan['radius'] = radius
            elif "radius" in self._cplan:
                radius = self._cplan["radius"]  # 转弯半径
                clockwise = 1  # 顺时针
                _az = course + 90 * clockwise
                center = alg.geo.reckon(coords, radius, _az)
                self._cplan['center'] = center
            else:
                raise RuntimeError("缺少必要的参数")
            points = np.array(alg.drive.turnPointsCal(
                coords, course, theta, center=center))
            self._cplan["points"] = points[1:]  # 去掉当前点
        elif self._cplan["mode"] == "maneuver8":  # 8字形
            self._repeat_times = self._cplan.get('repeat', np.inf)  # 重复次数
            coords = self.coords
            course = self.course
            az = self._cplan['az']
            clockwise = True if "clockwise" not in self._cplan else self._cplan["clockwise"]
            self._cplan["clockwise"] = clockwise
            if "center1" in self._cplan:
                assert len(self._cplan['center1']) == 3, "长度须为3"
                center1 = np.array(self._cplan['center1'])
                radius = alg.geo.distance(coords, center1)
                self._cplan['radius'] = radius
            elif "radius" in self._cplan:
                radius = self._cplan["radius"]  # 转弯半径
                clockwise = 1 if clockwise else -1
                _az = course + 90 * clockwise
                center1 = alg.geo.reckon(coords, radius, _az)
                self._cplan['center1'] = center1
            else:
                raise RuntimeError("缺少必要的参数")
            points = np.array(alg.drive.path8PointsCal(
                coords, course, az, center=center1, clockwise=clockwise))
            center2 = alg.geo.reckon(center1, 2*radius, az)
            self._cplan['center2'] = center2
            self._cplan["points"] = points[1:]  # 去掉当前点
        elif self._cplan['mode'] == 'turn':  # 转弯
            self._repeat_times = 1  # 不重复
            coords = self.coords
            course = self.course
            theta = self._cplan["theta"]  # 转弯角度
            radius = self._cplan["radius"]  # 转弯半径
            clockwise = True if "clockwise" not in self._cplan else self._cplan["clockwise"]
            self._cplan["clockwise"] = clockwise
            sign = 1 if clockwise else -1
            self._cplan["end_course"] = course+sign*theta
            points = np.array(alg.drive.turnPointsCal(
                coords, course, theta, radius=radius, clockwise=clockwise))
            self._cplan["points"] = points[1:]  # 去掉当前点
        elif self._cplan["mode"] == "recycle":  # 往复
            self._repeat_times = self._cplan.get('repeat', np.inf)  # 重复次数
            points = np.array(self._cplan["waypoints"])
            self._cplan["points"] = points
        elif self._cplan["mode"] == "coords":  # 飞向指定的位置
            self._repeat_times = 1  # 不重复
            coords = self._cplan["coords"].copy()
            points = np.array([coords])
        # elif self._cplan["mode"] == "target": #飞向指定的动态目标
        #     self._cplan['repeat'] = False #不重复
        #     self._target = self._cplan["target"] #target为目标对象，不是传感器探测到的目标track对象
        #     self._add_handler(LeadMsgBody, self._lead_handler)#添加对指挥引导指令的响应
        #     self._cplan["repeat"] = False
        else:
            raise RuntimeError("unknown coords plan %s" % self._cplan['mode'])
        self._points.extend(points)

    def _work(self):
        # 判断当前的机动计划是否执行完毕
        if not (self._cplan or self._splan or self._tcplan or self._simple_plan):
            if self._move_plans:
                cplan, splan, tcplan, simple_plan = self._move_plans.popleft()
                self._handle_move_plan(cplan, splan, tcplan, simple_plan)
        # 执行机动计划
        if self._simple_plan:
            if self.engine.tick >= self._end_tick:
                self._simple_plan = None
        if self._tcplan:
            self._quaternions_adjust()
        if self._splan:
            self._speed_adjust()  # 调整速度大小
        if self._cplan:
            self._course_adjust()  # 根据航路点调整速度方向

    def _quaternions_adjust(self):
        assert self._motor.state == "MOVE"
        t1, *pos1 = self._quaternions[0]
        period = self._motor._state_period
        # 如果速度很小，则最小取MIN_DIS=100m
        gap = max(self._motor.speed * period, MIN_DIS)
        if alg.geo.distance(self._motor.coords, pos1) < gap:
            self._quaternions.popleft()
            if self._quaternions:
                t2, *pos2 = self._quaternions[0]
                v = (np.array(pos2, dtype=np.float64) - self._motor.coords)/(t2-t1)
                self._motor.change_velocity(v)
            else:
                self._tcplan = None

    def _speed_adjust(self):
        """ 调整标量速度的大小
        """
        if self.engine.tick > self._end_tick:
            self._splan = None
            return
        if self._splan['mode'] == 'dfsq':
            # 吊放声呐作业:搜潜作业和飞行切换
            time_interval = self._state_period
            period = self._splan['fly_time'] + 2 * \
                self._splan["prepare_time"] + self._splan["work_time"]
            # current_time = self._motor.state_time % period
            current_time = (
                (self.engine.tick - self._upper_tick) / 1000.0) % period
            if 0 <= current_time < time_interval:
                self._motor.change_speed(self._splan['fly_speed'])
                self._is_adjust_course = True
            elif 0 <= current_time - self._splan['fly_time'] < time_interval:
                self._motor.change_speed(0)
                self._is_adjust_course = False
            elif 0 <= current_time - self._splan['fly_time'] - self._splan["prepare_time"] < time_interval:
                self.unit.sonars[0].scan()
            elif 0 <= current_time - self._splan['fly_time'] - self._splan["prepare_time"] - self._splan["work_time"] < time_interval:
                self.unit.sonars[0].stop()
        elif self._splan['mode'] == 'frog':  # 蛙跳
            time_interval = self._state_period
            current_time = self._motor.state_time % (
                self._splan['fast_time'] + self._splan['slow_time'])
            if 0 <= current_time < time_interval:
                self._motor.change_speed(self._splan['fast_speed'])
            elif 0 <= current_time - self._splan['fast_time'] < time_interval:
                self._motor.change_speed(self._splan['slow_speed'])
        else:
            raise RuntimeError("unknown velocity plan %s" % self._splan['mode'])

    def _course_adjust(self):
        if self._points:
            assert self._motor.state == "MOVE"
            period = self._state_period
            while self._points:
                # 如果多个点都满足条件，均pop
                if alg.geo.distance(self._motor.coords, self._points[0]) < self._motor.speed * period:
                    self._points.popleft()
                    self._is_adjust_course = True
                else:
                    break
        if self._points and self._is_adjust_course:
            v = alg.drive.velocity(
                self._motor.speed, self._motor.coords, self._points[0])
            self._motor.change_velocity(v)
            self._is_adjust_course = False
        if not self._points:
            self._repeat_times -= 1
            if self._repeat_times > 0:
                points = self._cplan["points"]
                self._points.extend(points)
                self._course_adjust()
            else:
                if self._cplan["mode"] == "turn":
                    end_course = self._cplan["end_course"]
                    self._motor.change_course(end_course)  # 调整航向，修正转弯后航向不合理的现象
                self._cplan = None

    def draw(self, ax):
        """ 绘制路线
        """
        if self._cplan:
            if self.engine.tick - self._upper_tick > 1000:
                # 绘制规划路线
                if self._cplan['mode'] == 'round':  # 环绕
                    center = np.array(self._cplan['center'])
                    radius = self._cplan['radius']
                    circle = alg.shape.Circle(center, radius)
                    circle.plot(ax, "--", c=self.group, linewidth=0.5)
                elif self._cplan['mode'] == 'maneuver8':  # 8字型机动
                    center1 = np.array(self._cplan['center1'])
                    center2 = np.array(self._cplan['center2'])
                    radius = self._cplan['radius']
                    circle = alg.shape.Circle(center1, radius)
                    circle.plot(ax, "--", c=self.group, linewidth=0.5)
                    circle = alg.shape.Circle(center2, radius)
                    circle.plot(ax, "--", c=self.group, linewidth=0.5)
                elif self._cplan['mode'] in ['turn', "recycle"]:  # 环绕
                    points = self._cplan["points"]
                    if points.shape[0] > 0:
                        ax.plot(points[:, 0], points[:, 1], "--",
                                c=self.group, linewidth=0.5)
                elif self._cplan["mode"] == "coords":
                    coords = self._cplan["coords"]
                    ax.plot(coords[0], coords[1], "*", c=self.group)
                    ax.text(coords[0], coords[1], "瞄准点")
                # 绘制剩余路线
                if self._points:
                    points = np.array(self._points)
                    if points.shape[0] > 0:
                        ax.plot(points[:, 0], points[:, 1], "-",
                                c=self.group, linewidth=0.5)

    def drawSymbol(self):
        if self._cplan is not None:
            x = []
            y = []
            if self._cplan['mode'] == 'round':  # 环绕
                coords = self._motor.coords
                center = np.array(self._cplan['center'])
                radius = alg.geo.distance(coords, center)
                rad = np.array([i / 180 * np.pi for i in range(361)])
                x = center[0] + radius * np.sin(rad)
                y = center[1] + radius * np.cos(rad)
            elif self._cplan['mode'] == 'maneuver8':  # 8字型机动
                points = self._cplan["points"]
                x, y, z = points.T.tolist()
            elif self._cplan['mode'] == 'turn':  # 环绕
                if self._points:
                    for point in self._points:
                        x.append(point[0])
                        y.append(point[1])
            elif self._cplan["mode"] == "recycle":
                points = np.array(self._cplan["waypoints"])
                for a, b, c in points:
                    x.append(a)
                    y.append(b)
            # else:
            #     raise RuntimeError("unkown coords plan %s" % self._cplan['mode'])
            symbol = alg.shape.Symbol(
                mode="Line", x=x, y=y, color=self.group)
            return [symbol]


class BoidDriver(core.arch.Driver):
    """ 自动运动
    """

    def _fly_toward_center(self):
        coords = np.array([0.0, 0.0, 0.0])
        numNeighbors = 0
        neighbors = self._companions | set([self])
        for driver in neighbors:
            if alg.geo.distance(self.coords, driver.coords) < self.attr.visual_range:
                coords += driver.coords
                numNeighbors += 1
        if numNeighbors > 0:
            coords = coords / numNeighbors
            dv = (coords - self.coords) * self.attr.centering_factor
            self._motor.change_velocity(self.velocity+dv)

    def _avoid_others(self):
        coords = np.array([0.0, 0.0, 0.0])
        neighbors = self._companions | set([self._leader])
        for driver in neighbors:
            if alg.geo.distance(self.coords, driver.coords) < self.attr.min_distance:
                coords += self.coords - driver.coords
        dv = coords * self.attr.avoid_factor
        self._motor.change_velocity(self.velocity+dv)

    def _match_velocity(self):
        velocity = np.array([0.0, 0.0, 0.0])
        numNeighbors = 0
        neighbors = self._companions | set([self, self._leader])
        for driver in neighbors:
            if alg.geo.distance(self.coords, driver.coords) < self.attr.visual_range:
                velocity += driver.velocity
                numNeighbors += 1
        if numNeighbors > 0:
            velocity = velocity / numNeighbors
            dv = (velocity - self.velocity) * self.attr.matching_factor
            self._motor.change_velocity(self.velocity+dv)

    def _limit_speed(self):
        if self.speed > self.attr.speed_limit:
            v = self.attr.speed_limit/self.speed*self.velocity
            self._motor.change_velocity(v)

    def _keep_in_bounds(self):
        x1, x2 = self.engine.render_config.get("xlim", [0, 10000])
        y1, y2 = self.engine.render_config.get("ylim", [0, 10000])
        v = self.velocity.copy()
        if self.coords[0] > x2 or self.coords[0] < x1:
            v[0] = -v[0]
        if self.coords[1] > y2 or self.coords[1] < y1:
            v[1] = -v[1]
        self._motor.change_velocity(v)

    def _follow_leader(self):
        behind = self._leader.coords - \
            (self._leader.velocity/self._leader.speed)*self.attr.leader_dis
        dv = (behind - self.coords) * self.attr.follow_factor
        self._motor.change_velocity(self.velocity+dv)

    def _evade_leader(self):
        ahead = self._leader.coords + \
            (self._leader.velocity/self._leader.speed)*self.attr.leader_dis
        if (alg.geo.distance(self.coords, ahead) <= self.attr.leader_sight):
            # or alg.geo.distance(self.coords, self._leader.coords) <= self.attr.leader_sight):
            dv = (self.coords - ahead) * self.attr.follow_factor
            self._motor.change_velocity(self.velocity+dv)

    def _work(self):
        assert self.role == "subordinate"
        self._keep_in_bounds()
        # keep_in_bounds函数必须在前，或者更合理的方式应该是速度最后统一改，而不是随时改
        self._follow_leader()
        self._fly_toward_center()
        self._avoid_others()
        self._match_velocity()
        self._evade_leader()
        self._limit_speed()

    def check(self):
        assert self.role in ["subordinate", "leader"]
        # default 0.01, adjust velocity by this
        assert self.attr.has_attr("centering_factor")
        assert self.attr.has_attr("visual_range")
        # default 20, the distance to stay away from other boids
        assert self.attr.has_attr("min_distance")
        # default 0.05, adjust velocity by this
        assert self.attr.has_attr("avoid_factor")
        # default 0.05, adjust by this of average velocity
        assert self.attr.has_attr("matching_factor")
        assert self.attr.has_attr("speed_limit")
        assert self.attr.has_attr("leader_dis")
        assert self.attr.has_attr("leader_sight")
        assert self.attr.has_attr("follow_factor")
        assert self.attr.has_attr("evade_factor")


class ShipDriver(NormalDriver):
    def __init__(self, unit, model):
        super().__init__(unit, model)
        self._speed_df = self.engine.db[self.attr.speed_data]
        self._turn_df = self.engine.db[self.attr.turn_data]
        self._inertia_df = self.engine.db[self.attr.inertia_data]
        self._main_engine = self.attr.main_engine  # 主机
        self._working_condition = None  # 工况, 初始状态为None
        self._working_condition_log = collections.deque()  # 未来的工况序列
        self._is_back_log = collections.deque()  # 未来的是否倒车状态序列
        self._dplan = None  # 当前的驾驶计划
        self._dplan_num = 0  # 当前的驾驶计划对应的分解机动计划数量
        self._drive_plans = collections.deque()  # 驾驶计划序列

    def set_move_plan(self, cplan=None, splan=None, tcplan=None, simple_plan=None, mode="clear"):
        raise RuntimeError("禁用该方法")

    def set_drive_plan(self, dplan, mode="clear"):
        if mode == "clear":
            self._cplan = None
            self._splan = None
            self._tcplan = None
            self._simple_plan = None
            self._dplan = None
            self._dplan_num = 0
            self._drive_plans.append(dplan)
            self._work()  # 立即工作
        else:
            self._drive_plans.append(dplan)

    def _query_speed(self, cmd):
        df = self._speed_df
        df = df[df["主机"] == self._main_engine]
        assert cmd in set(df["工况"].values)
        df = df[df["工况"] == cmd]
        speed = df.values[0][-1]*1.852/3.6  # 节转换为m/s
        tag = 1  # 速度方向是否与原方向相反(倒车),1:相同,-1:相反
        if (self._working_condition is None) or ("停车" in self._working_condition):
            if "进" in cmd:
                tag = 1
            elif "退" in cmd:
                tag = -1
            else:
                raise RuntimeError("工况不合理")
        elif "退" in self._working_condition:
            if "进" in cmd or "停车" in cmd:
                tag = -1
            elif "退" in cmd:
                tag = 1
            else:
                raise RuntimeError("工况不合理")
        elif "进" in self._working_condition:
            if "退" in cmd or "停车" in cmd:
                tag = -1
            elif "进" in cmd:
                tag = 1
            else:
                raise RuntimeError("工况不合理")
        else:
            raise RuntimeError("工况不合理")
        return speed*tag

    def _query_inertia(self, wc1, wc2):  
        df = self._inertia_df
        df = df[df["主机"] == self._main_engine]
        flag = wc1 + ":" + wc2
        if flag in set(df["工况"].values):
            df = df[df["工况"] == flag]
            inertia_dis = df.values[0][-1]
            inertia_time = df.values[0][-2]
            return inertia_dis, inertia_time
        else:
            return None

    def _query_turn(self, wc, duojiao):
        df = self._turn_df
        df = df[df["主机"] == self._main_engine]
        assert wc in set(df["工况"].values)
        df = df[df["工况"] == wc]
        assert duojiao in set(df["舵角(度)"].values)
        df = df[df["舵角(度)"] == duojiao]
        speed = df.values[0][3]*1.852/3.6  # 节转换为m/s
        r = df.values[0][4]*0.5  # 半径
        return speed, r

    def _handle_drive_plan(self, dplan):
        assert self._working_condition not in [
            "惯性", "转弯"], "可能是下达clear模式命令的时机不对"
        self._dplan = dplan
        if dplan["mode"] == "speed":
            cmd = dplan["cmd"]
            duration = dplan.get("duration", 0)  # 持续时间(不含惯性时间)
            speed = self._query_speed(cmd)
            if self._working_condition is None:
                # 初始状态不考虑惯性, 但考虑前进后退
                sign = -1 if "退" in cmd else 1
                is_back = True if "退" in cmd else False
                super().set_move_plan(simple_plan={
                    "mode": "speed", "speed": speed*sign, "duration": duration}, mode="append")
                self._working_condition_log.append(cmd)
                self._is_back_log.append(is_back)
                self._dplan_num = 1
            else:
                out = self._query_inertia(self._working_condition, cmd)
                if out:
                    inertia_dis, inertia_time = out
                    # assert duration > inertia_time, f"{cmd}的持续时间应大于惯性时间{inertia_time:.2f}" # 持续时间不含惯性时间
                    # 双段加速，每段加速时间各为总时间的一半，计算每段的加速度
                    v1 = self.speed
                    v2 = speed
                    t = inertia_time
                    d = inertia_dis
                    a2 = (v2-v1)/t-4*d/(t**2)+2*(v1+v2)/t
                    a1 = 2*(v2-v1)/t-a2
                    acce1 = a1/self.speed*self.velocity
                    acce2 = a2/self.speed*self.velocity
                    # import pdb; pdb.set_trace()
                    num = 0
                    if a1 < 0 and -v1/a1 < t/2:
                        super().set_move_plan(simple_plan={
                            "mode": "acce", "acce": acce1, "duration": -v1/a1}, mode="append")
                        self._working_condition_log.append("惯性")
                        self._is_back_log.append(self.unit.motor.is_back)
                        num += 1
                        super().set_move_plan(simple_plan={
                            "mode": "acce", "acce": acce1, "duration": t/2+v1/a1}, mode="append")
                        self._working_condition_log.append("惯性")
                        self._is_back_log.append(not self._is_back_log[-1])
                        num += 1
                    else:
                        super().set_move_plan(simple_plan={
                            "mode": "acce", "acce": acce1, "duration": t/2}, mode="append")
                        self._working_condition_log.append("惯性")
                        self._is_back_log.append(self.unit.motor.is_back)
                        num += 1
                    v_mid = v1 + a1*inertia_time/2  # 中间时刻的速度
                    if v_mid*a2 < 0 and -v_mid/a2 < inertia_time/2:
                        super().set_move_plan(simple_plan={
                            "mode": "acce", "acce": acce2, "duration": -v_mid/a2}, mode="append")
                        self._working_condition_log.append("惯性")
                        self._is_back_log.append(self._is_back_log[-1])
                        num += 1
                        super().set_move_plan(simple_plan={
                            "mode": "acce", "acce": acce2, "duration": t/2+v_mid/a2}, mode="append")
                        self._working_condition_log.append("惯性")
                        self._is_back_log.append(not self._is_back_log[-1])
                        num += 1
                    else:
                        super().set_move_plan(simple_plan={
                            "mode": "acce", "acce": acce2, "duration": t/2}, mode="append")
                        self._working_condition_log.append("惯性")
                        self._is_back_log.append(self._is_back_log[-1])
                        num += 1
                    super().set_move_plan(simple_plan={"mode": "acce", "acce": [
                        0, 0, 0], "duration": duration}, mode="append")
                    self._working_condition_log.append(cmd)
                    self._is_back_log.append(self._is_back_log[-1])
                    num += 1
                    self._dplan_num = num
                else:
                    # 按默认惯性加速度处理，并考虑前进和后退
                    v1 = self.speed
                    v2 = speed
                    t = abs(v2-v1)/self.attr.default_acce
                    # assert duration >= t, f"{cmd}的持续时间应大于惯性时间{t:.2f}" # 持续时间不含惯性时间
                    a = np.sign(v2-v1)*self.attr.default_acce
                    acce = a/self.speed*self.velocity
                    num = 0
                    if a < 0 and -v1/a < t:
                        super().set_move_plan(simple_plan={
                            "mode": "acce", "acce": acce, "duration": -v1/a}, mode="append")
                        self._working_condition_log.append("惯性")
                        self._is_back_log.append(self.unit.motor.is_back)
                        num += 1
                        super().set_move_plan(simple_plan={
                            "mode": "acce", "acce": acce, "duration": t+v1/a}, mode="append")
                        self._working_condition_log.append("惯性")
                        self._is_back_log.append(not self._is_back_log[-1])
                        num += 1
                    else:
                        super().set_move_plan(simple_plan={
                            "mode": "acce", "acce": acce, "duration": t}, mode="append")
                        self._working_condition_log.append("惯性")
                        self._is_back_log.append(self.unit.motor.is_back)
                        num += 1
                    super().set_move_plan(simple_plan={"mode": "acce", "acce": [
                        0, 0, 0], "duration": duration}, mode="append")
                    self._working_condition_log.append(cmd)
                    self._is_back_log.append(self._is_back_log[-1])
                    num += 1
                    self._dplan_num = num
        elif dplan["mode"] == "turn":
            assert "进" in self._working_condition  # 只有在前进状态下才能转弯
            assert not self.unit.motor.is_back  # 只有在前进状态下才能转弯,与上句等价
            duojiao = dplan["duojiao"]  # 舵角
            theta = dplan["theta"]  # 转弯角度
            clockwise = dplan.get("clockwise", True)
            speed, r = self._query_turn(self._working_condition, duojiao)
            super().set_move_plan(simple_plan={
                "mode": "speed", "speed": speed}, mode="append")
            super().set_move_plan(cplan={
                "mode": "turn", "radius": r, "theta": theta, "clockwise": clockwise}, mode="append")
            speed = self._query_speed(self._working_condition)
            super().set_move_plan(simple_plan={
                "mode": "speed", "speed": speed}, mode="append")
            self._working_condition_log.extend(
                ["转弯", "转弯", self._working_condition])
            self._is_back_log.extend([False, False, False])
            self._dplan_num = 3
        else:
            raise RuntimeError("unknown drive plan mode")

    def _work(self):
        # 判断当前的机动计划和驾驶计划是否执行完毕
        if not (self._cplan or self._splan or self._tcplan or self._simple_plan):
            if self._dplan_num == 0:
                self._dplan = None
                if self._drive_plans:
                    dplan = self._drive_plans.popleft()
                    self._handle_drive_plan(dplan)
                    # 日志输出
                    if dplan["mode"] == "speed":
                        s = f" 直航 切换工况[{dplan['cmd']}] 持续时间[{dplan.get('duration', 0)}s]"
                    elif dplan["mode"] == "turn":
                        s = f" 转弯 舵角[{dplan['duojiao']}度] 转弯角度[{dplan['theta']}度]"
                    self.engine.log_decision("机动指令 "+s)
            if self._move_plans:
                cplan, splan, tcplan, simple_plan = self._move_plans.popleft()
                self._handle_move_plan(cplan, splan, tcplan, simple_plan)
                # 更新工况, 否则停留在上一个状态
                self._working_condition = self._working_condition_log.popleft()
                self.unit.motor.is_back = self._is_back_log.popleft()
                flag = "后退" if self.unit.motor.is_back else "前进"
                self._dplan_num -= 1
                if self._dplan_num < 1:
                    wc = self._working_condition
                else:
                    wc = self._working_condition_log[self._dplan_num-1] + \
                        "[" + self._working_condition + "]"
                a = np.linalg.norm(self.acce)
                self.engine.log_decision(
                    f"分解指令 工况:{wc}[{flag}] 速度:{self.speed:.2f}m/s {self.speed*3.6/1.852:.2f}节 加速度:{a:.5f}m/s^2")

        # 执行机动计划
        if self._simple_plan:
            if self.engine.tick >= self._end_tick:
                self._simple_plan = None
        if self._tcplan:
            self._quaternions_adjust()
        if self._splan:
            self._speed_adjust()  # 调整速度大小
        if self._cplan:
            self._course_adjust()  # 根据航路点调整速度方向

    def check(self):
        assert self.unit.motor.__class__.__name__ == "ShipMotor"


class Driver052D(ShipDriver):
    pass


class Driver054A(Driver052D):
    def __init__(self, unit, model):
        super().__init__(unit, model)
        self._sailing_mode = self.attr.sailing_mode

    def _query_inertia(self, wc1, wc2):
        df = self._inertia_df
        df = df[df["航行模式"] == self._sailing_mode]
        flag = wc1 + ":" + wc2
        if flag in set(df["工况"].values):
            df = df[df["工况"] == flag]
            inertia_dis = df.values[0][2]
            inertia_time = df.values[0][3]
            return inertia_dis, inertia_time
        else:
            return None

    def check(self):
        assert self.unit.motor.__class__.__name__ == "ShipMotor"
        assert self._main_engine == "柴油机"


class FixedWingDriver(core.arch.Driver):
    def __init__(self, unit, model):
        super().__init__(unit, model)
        self._keep_dis = None  # 与领航保持的距离（m）
        self._keep_angle = None  # 与领航保持的角度（度）
        self._chase_points = None  # 伴航的追逐点坐标（绘图用）
        self._leader_speed = None  # 主机在伴飞模式中的起始速度
        self.subordinates_follow_info = {}
        # "Undefined":, "Followed":, "FreeFly", "Following"
        self.flag1 = False
        self.flag2 = False

    def get_subordinate(self):
        """ 返回主机的伴航成员
        """
        return self._subordinates

    def set_leader(self, driver, keep_dis, keep_angle):
        """ 设置领队

        Args:
            driver (_type_): _description_
            keep_dis (_type_): _description_
            keep_angle (_type_): _description_
        """
        super().set_leader(driver)
        driver.subordinates_follow_info[self] = "Undefined"
        self._keep_dis = keep_dis
        self._keep_angle = keep_angle

    def set_keep_dis_angle(self, driver, keep_dis, keep_angle):
        assert self.role == "subordinate"
        driver.subordinates_follow_info[self] = "Undefined"
        self._keep_dis = keep_dis
        self._keep_angle = keep_angle

    def _work(self):
        """ 根据不同的角色切换到不同的状态
        """
        # 如果未起飞或在起飞爬升过程中
        if self.unit.is_at_home:
            return
        # 如果是主机
        if self.role == "leader":
            if self._motor.mode in ["TakeOff"]:
                return
            if self._motor.mode is None and self._motor.get_next_mode() in ["TakeOff"]:
                return
            self._change_state("Lead")
            return
        # 如果不是主机也不是僚机
        elif self.role == "ordinary":
            return
        else:
            # 如果是僚机
            if self._motor.mode in ["TakeOff", "Climb"]:
                return
            if self._motor.mode is None and self._motor.get_next_mode() in ["TakeOff", "Climb"]:
                return
            if not self._leader.isactive:
                return
            if self._leader.unit.is_at_home:
                return
            self._change_state("Follow")

    def is_all_followed(self):
        """ 判断主机的所有僚机是否都已集结完毕
        """
        assert self._role == "leader"
        for k, v in self.subordinates_follow_info.items():
            if v in ["Following", "Undefined"]:
                return False
        return True

    def _leader_fly(self):
        # import pdb; pdb.set_trace()
        if not self.is_all_followed():
            begin_hover = True
            if self._motor.mode == "Hover":
                begin_hover = False
            if self._motor.mode is None and self._motor.get_next_mode() == "Hover":
                begin_hover = False
            if begin_hover:
                # hover_radius = 5000
                self._motor.insert_maneuver_cmd(
                    {"mode": "Hover"})
        else:
            # 停止Hover，并拷贝剩余的机动指令
            temp_cmds = self.unit.motor._maneuver_cmds.copy()
            self.unit.motor.clear_cmds()
            self.unit.motor._maneuver_cmds = temp_cmds

    # 伴航飞机跟随领航飞机
    def _follow_init(self):
        self._motor.clear_cmds()
        msg = message.msg.MsgFollow("Following")
        self._send_msg(self._leader, msg)

    def _follow_leader(self):
        coords = self._leader.coords
        course = self._leader.course
        az = course + self._keep_angle
        dis = self._keep_dis
        follow_coords = alg.geo.reckon(coords, dis, az)  # 追逐点坐标
        self._chase_points = follow_coords
        va_next = self._leader.velocity
        vb_next = va_next*self.speed/self._leader.speed
        vb_now = self.velocity

        theta = (alg.fol2d.angle_theta((follow_coords - self.coords).reshape(1, 3)) -
                 alg.fol2d.angle_theta(vb_now.reshape(1, 3))) % 360  # 目标点与v_now之间的夹角，逆时针为正，单位: 角度制
        clockwise = False
        if theta > 180:  # 速度夹角大于180度
            theta = 360 - theta  # 计算在顺时针的角度
            clockwise = True
        if theta > 90:  # 最大转向角度限制[-90,90]
            theta = 90
        # print(f'theta: {theta}')
        assert self.speed > 0, "speed == 0"

        err_dis = alg.geo.distance(follow_coords, self.coords)
        err_speed = np.linalg.norm(self._leader.speed - self.speed)

        if theta > 10:  # 角度大于10度开始修正
            acce_n = (vb_next - vb_now)/self._state_period
            acce_n_norm = np.linalg.norm(acce_n)
            if acce_n_norm > self._motor.attr.max_acce_n:  # 最大法向加速度约束
                acce_n = acce_n*self._motor.attr.max_acce_n/acce_n_norm
            if acce_n_norm < 0.01:
                radius_b = np.linalg.norm(
                    vb_next - vb_now)*self._motor.attr.max_acce_n/theta
            else:
                radius_b = self.speed*self.speed/acce_n_norm

            self._motor.insert_maneuver_cmd(
                {"mode": "Turn", "theta": theta, "turn_radius": radius_b, "clockwise": clockwise}, rightnow=True)  # 立刻转弯
            # print(
            #     f'Turn,theta:{theta},radius_b:{radius_b},clockwise:{clockwise}')
        # 满足能够速度差过大无法及时减速，或距离偏差较小，以控制速度为目标
        elif err_speed**2/err_dis > 0.5*self._motor.attr.max_acce_s or err_dis < 0.5*self._motor.attr.max_speed:
            msg = message.msg.MsgFollow("Following")
            if err_dis < self._motor.attr.max_speed:
                msg = message.msg.MsgFollow("Followed")
                self._send_msg(self._leader, msg)
            self._send_msg(self._leader, msg)
            acce_s = (self._leader.velocity - self.velocity)/self._state_period
            acce_s_norm = np.linalg.norm(acce_s)
            # print(f'Acce2,{acce_s}')
            if acce_s_norm > self._motor.attr.max_acce_s:
                acce_s = acce_s*self._motor.attr.max_acce_s/acce_s_norm
            vb = self.velocity + acce_s*self._state_period
            vb_norm = np.linalg.norm(vb)
            if vb_norm > self._motor.attr.max_speed*0.9:
                acce_s = (vb*self._motor.attr.max_speed*0.9/vb_norm -
                          self.velocity)/self._state_period
            self._motor.insert_maneuver_cmd(
                {"mode": "acce", "acce": acce_s}, rightnow=True)
            # print(f'Acce2,{acce_s}')
        # 以控制位置为目标
        else:
            msg = message.msg.MsgFollow("Following")
            if err_dis < self._motor.attr.max_speed:
                msg = message.msg.MsgFollow("Followed")
                self._send_msg(self._leader, msg)
            self._send_msg(self._leader, msg)
            error_dis = (follow_coords-self.coords) - \
                (self.velocity - self._leader.velocity)*self._state_period
            acce_s = 2*error_dis/self._state_period**2
            acce_s_norm = np.linalg.norm(acce_s)
            acce_s = acce_s_norm*self.velocity/self.speed
            # print(f'Acce1,{acce_s}')
            acce_s = acce_s*err_dis/self._keep_dis
            if acce_s_norm > self._motor.attr.max_acce_s:
                acce_s = acce_s*self._motor.attr.max_acce_s/acce_s_norm
            vb = self.velocity + acce_s*self._state_period
            vb_norm = np.linalg.norm(vb)
            if vb_norm > self._motor.attr.max_speed*0.9:
                acce_s = (vb*self._motor.attr.max_speed*0.9/vb_norm -
                          self.velocity)/self._state_period
            self._motor.insert_maneuver_cmd(
                {"mode": "acce", "acce": acce_s}, rightnow=True)
            # print(f'Acce1,{acce_s}')

        # print(
        #     f'leader_pos:{self._leader.coords},leader_v:{self._leader.velocity}')
        # print(f'sub_pos:{self.coords},sub_v:{self.velocity}')
        # print(f'follow_coords:{follow_coords}')
        # print(f'Name:{self.unit.name}\n')

    def _freefly_init(self):
        msg = message.msg.MsgFollow("FreeFly")
        self._send_msg(self._leader, msg)

    def _return_to_base_handler(self, event):
        if event.flag == "Begin":
            point = self.unit.home_unit.coords.copy()
            point[2] = self.coords[2]
            self._motor.clear_cmds()
            self._motor.add_maneuver_cmd(
                {"mode": "ReturnToBase", "waypoints": [point]})
            # import pdb; pdb.set_trace()
        else:
            # event.flag == "End"
            msg = message.msg.MsgLandOnRequset(self.unit)
            self._motor.clear_cmds(is_clear_current = False)
            self._motor.add_maneuver_cmd({"mode": "Hover"})
            self._send_msg(self.unit.home_unit.airportsystem,
                           msg, isignored=False)

    def _land_on_echo_handler(self, msg):
        assert msg.flag == "Yes"
        print("receive echo",self.engine.tick)
        # 为简化起见，暂时忽略下降过程，直接着陆
        self._motor.clear_cmds(is_clear_current = False)
        self._motor.insert_maneuver_cmd({"mode": "LandOn"})

    def _follow_handler(self, msg):
        if msg.flag == "Followed":
            self.subordinates_follow_info[msg.src] = "Followed"
        elif msg.flag == "FreeFly":
            self.subordinates_follow_info[msg.src] = "FreeFly"
        elif msg.flag == "Following":
            self.subordinates_follow_info[msg.src] = "Following"
        else:
            self.engine.log_error(f"未定义的flag:{self.flag}")

    def implement(self):
        # 新增添两种状态，Follow状态可以让伴航飞机开始伴航模式，
        # FreeFly可以让伴航飞机自由飞行
        self._add_state("Lead", self._leader_fly,
                        repeat=self.attr.period)
        self._add_state("Follow", self._follow_leader,
                        repeat=self.attr.period, init=self._follow_init)
        self._add_state("FreeFly", lambda: None,
                        repeat=0, init=self._freefly_init)
        self._add_state("Work", self._work, repeat=self.attr.period)
        self._add_transfer("FREE",  "Work", lambda: True)
        self._add_handler("EventReturnToBase", self._return_to_base_handler)
        self._add_handler("MsgLandOnEcho", self._land_on_echo_handler)
        self._add_handler("MsgFollow", self._follow_handler)
        return self

    def draw(self, ax):
        if self._chase_points is not None:
            x, y, _ = self._chase_points
            ax.scatter(x, y, c=self.group.lower(), s=20, alpha=0.5)

    def check(self):
        if self.role in ["subordinate", "leader"]:
            assert self._motor.attr.has_attr("max_acce_s"), self._motor
            assert self._motor.attr.has_attr("max_speed"), self._motor
            assert self._motor.attr.has_attr("max_acce_n"), self._motor
