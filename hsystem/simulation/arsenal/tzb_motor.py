import numpy as np
import copy
from .. import algorithm as alg
from .. import message
from ..core.arch import Motor
from .motor import WaypointsMotor, ManeuverMotor
from ..core import special_effect


class MotorTZB(ManeuverMotor):

    def __init__(self, unit, model):
        super().__init__(unit, model)
        self.is_back = False
        self.is_frozen = False
        self.plat_at_home = False
        self.plat_home_name = None

    def set_at_home(self, home_name):
        if not self.plat_at_home:
            self.plat_at_home = True
            self.plat_home_name = home_name

    def remove_home(self):
        if self.plat_at_home:
            self.plat_at_home = False
            self.plat_home_name = None

    def set_frozen(self):
        if not self.is_frozen:
            self.is_frozen = True

    def frozen_release(self):
        if self.is_frozen:
            self.is_frozen = False

    def set_motivate_param(self,coords, velocity=[0, 0, 0]):
        super().set_motivate_param(coords, velocity=velocity)
        self.real_angle = np.deg2rad(self.course)
        self.real_speed = self.speed
        self.max_angle_velocity = self.attr.max_angle_velocity
        self.max_speed = self.attr.max_speed
        self.max_acce = self.attr.max_acce
        self.target_angle = None
        self.target_speed = None

    def set_target_angle(self, angle):
        self.target_angle = np.deg2rad(angle)

    def set_target_speed(self, speed):
        self.target_speed = max(speed, 0)

    def get_ship_state(self):
        state = {
            "course": np.rad2deg(self.real_angle),
            "speed": self.real_speed,
            "position": list(self.coords),
            "velocity": list(self.velocity)
        }
        return state

    def _move(self):
        if self.plat_at_home:
            plat_home = self.engine.unit_by_name(self.plat_home_name)
            self._coords = copy.deepcopy(plat_home.coords)
            self.real_speed = copy.deepcopy(plat_home.speed)
            self._velocity = copy.deepcopy(plat_home.velocity)
            self._last_course = copy.deepcopy(plat_home.course)
            # special_effect.EntityEffect.update(self.engine, self.unit.name)
            return
        if self.is_frozen:
            return
        if self._ref_unit:
            return
        period = self._state_period
        assert period > 0
        # 转向
        if self.target_angle is not None:
        #     if abs(self.target_angle - self.real_angle) < self.max_angle_velocity * period:
        #         self.real_angle = self.target_angle
        #         self.target_angle = None
        #     else:
        #         self.real_angle += np.sign(self.target_angle - self.real_angle) * self.max_angle_velocity * period
            cw_diff = (self.target_angle - self.real_angle) % (2*np.pi)
            ccw_diff = (self.real_angle - self.target_angle) % (2*np.pi)
            if cw_diff <= self.max_angle_velocity * period or ccw_diff <= self.max_angle_velocity * period:
                self.real_angle = self.target_angle
                self.target_angle = None
            else:
                if cw_diff <= ccw_diff:
                    self.real_angle += self.max_angle_velocity * period
                else:
                    self.real_angle -= self.max_angle_velocity * period

        # 加速
        if self.target_speed is not None:
            if abs(self.target_speed - self.real_speed) < self.max_angle_velocity * period:
                self.real_speed = self.target_speed
                self.target_speed = None
            else:
                self.real_speed += np.sign(self.target_speed -self.real_speed) * self.max_acce * period
            self.real_speed = max(min(self.real_speed, self.max_speed), -self.max_speed)
        # 位置改变
        self._velocity = np.array([self.real_speed*np.sin(self.real_angle), self.real_speed*np.cos(self.real_angle), 0])
        self._coords += self._velocity * period
        self._last_course = self.real_angle
        self._lnglath[0], self._lnglath[1] = self.engine.xy2lnglat(self._coords[0], self._coords[1])
        special_effect.EntityEffect.update(self.engine, self.unit.name)

        if self._num_waypoint == 0:
            # 没有航路点
            return

        while self._next_waypoint_id < self._num_waypoint:
            if alg.geo.distance(self.coords[0:2], np.array(self._waypoints[self._next_waypoint_id,0:2])) < 2*self.real_speed*period: # 1.2为经验扩大系数
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

            target_course = np.rad2deg(np.arctan2(velocity[0], velocity[1]))
            target_speed = alg.geo.norm3d(velocity)
            self.set_target_angle(target_course)
            self.set_target_speed(target_speed)

    def _set_waypoints(self, waypoints, speeds = None, speed = None, events = None):
        """ 设置航路点以及速度 """
        self._waypoints = np.array(waypoints)
        self._next_waypoint_id = 0
        self._num_waypoint = len(waypoints)  # waypoints的类型为list或np.array均可以
        if speeds is not None:
            self._speeds = speeds
        elif speed is not None:
            self._speeds = [speed] * self._num_waypoint
        else:
            self._speeds = [self.speed] * self._num_waypoint
        if events is not None:
            assert len(events) == self._num_waypoint
            self._events = events

        # 解决初始点与当前位置一致或非常接近的问题
        period = self._state_period
        period = 1 if period <= 0 else period
        while self._next_waypoint_id < self._num_waypoint:
            if alg.geo.distance(self.coords,
                        np.array(self._waypoints[self._next_waypoint_id, :])) < 1.2 * self.speed * period:  # 1.2为经验扩大系数
                if self._events:
                    content = message.event.EventManeuver(self._events[self._next_waypoint_id],
                                                          self._waypoints[self._next_waypoint_id, :])
                    self._send_event(self.unit.commander, content)  # 设置机动事件时必须有指挥员
                self._next_waypoint_id += 1
            else:
                break
        if self._next_waypoint_id == self._num_waypoint:
            # 由于给定的位置与当前位置非常接近，直接走完。但基于waypoints的机动指令的结束行为仍然执行
            self.engine.log_warning(f"{self.ucname}由于给定的位置与当前位置非常接近，直接走完")
            return
        velocity = alg.drive.velocity3(self._speeds[self._next_waypoint_id], self.coords,
                                       self._waypoints[self._next_waypoint_id, :])
        target_course = np.rad2deg(np.arctan2(velocity[0], velocity[1]))
        target_speed = alg.geo.norm3d(velocity)
        self.set_target_angle(target_course)
        self.set_target_speed(target_speed)
        self._current_waypoint_id = self._next_waypoint_id
