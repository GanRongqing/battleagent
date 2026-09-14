import numpy as np
from .. import algorithm as alg
from .. import message
from ..core import message as cmsg
from ..core.arch import Motor
from .motor import WaypointsMotor, ManeuverMotor
from .platform import Ship, Plane
from ..core import special_effect
from .. import core
from shapely import geometry


class JudgeSystem(core.entity.FSM):
    def __init__(self, engine, model):
        super().__init__(engine, engine)
        self.attr = core.arch.Attribute(self, engine.db[model])
        self.model = model
        assert self.__class__.__name__ == self.attr["class"]
        self.name = "挑战杯裁判系统"
        self.units = None
        self.units_all = None
        self.black_ships = set()
        self.white_ships = set()
        self.white_planes = set()
        self.black_planes = set()
        self.area = None
        self.enemy_area = None   # 仅敌方 BLUE 使用的 OOB 区域（实验用；None=与 area 相同）
        self.destination = 50_000
        self.black_locked_num = 0
        self.white_locked_num = 0
        self.coords = [np.nan, np.nan, np.nan]
        self.black_success = []
        self.collide_num = 0
        # 累计奖励计数器
        self.cumulative_score = {
            "black_killed": 0,       # 击沉黑方艇
            "white_ship_killed": 0,  # 白方艇被击沉
            "white_uav_killed": 0,   # 白方无人机被击毁
            "black_breakthrough": 0,  # 黑方突破
            "black_hit": 0,          # 黑方被命中(冻结)
            "white_hit": 0,          # 白方被命中(冻结)
            "collision": 0,          # 碰撞次数
        }

    def set_units(self, units):
        self.units = set(units)
        self.units_all = self.units.copy()
        for unit in self.units:
            if isinstance(unit, Ship) and unit.group == "BLUE":
                self.black_ships.add(unit)
            elif isinstance(unit, Ship) and unit.group == "RED":
                self.white_ships.add(unit)
            elif isinstance(unit, Plane) and unit.group == "RED":
                self.white_planes.add(unit)
            elif isinstance(unit, Plane) and unit.group == "BLUE":
                self.black_planes.add(unit)
            else:
                raise RuntimeError(f"裁判系統set_units,输入了不支持类型的平台:{unit}")

    def set_area(self, points):
        self.area = geometry.Polygon(points)

    def set_enemy_area(self, points):
        """仅敌方（BLUE）使用的 OOB 区域（默认 None = 与 area 相同）。

        用于"OOB multiplier"实验：放宽敌方 OOB 判定，不影响我方。
        """
        self.enemy_area = geometry.Polygon(points) if points else None


    def _judge(self):
        # 判断死亡
        dead_units = []
        for unit in self.units:
            if not unit.isactive:
                dead_units.append(unit)
        for unit in dead_units:
            self.units.remove(unit)
            if unit in self.black_ships:
                self.black_ships.remove(unit)
                self.cumulative_score["black_killed"] += 1
            elif unit in self.white_ships:
                self.white_ships.remove(unit)
                self.cumulative_score["white_ship_killed"] += 1
            elif unit in self.white_planes:
                self.white_planes.remove(unit)
                self.cumulative_score["white_uav_killed"] += 1
            elif unit in self.black_planes:
                self.black_planes.remove(unit)
                self.cumulative_score["black_uav_killed"] = self.cumulative_score.get("black_uav_killed", 0) + 1
            else:
                raise RuntimeError(f"{unit}不在任何阵营中，无法去除！")

        # 判断突防成功数量
        if self.destination is not None:
            for unit in self.black_ships:
                if unit.coords[0] <= self.destination:
                    print(f"{unit}突防成功！")
                    self.black_success.append(unit.name)
                    self.cumulative_score["black_breakthrough"] += 1
                    unit.kill()

        # 判断碰撞
        for white_ship in self.white_ships:
            for unit in self.units:
                if (isinstance(unit, Ship) and (white_ship != unit)
                        and alg.geo.distance(white_ship.coords, unit.coords) <= self.attr.ship_collide_distance):
                    print(f"{white_ship}和{unit}发生碰撞！")
                    self.collide_num += 1
                    self.cumulative_score["collision"] += 1

        # 判断是否在区域中
        if self.area is not None:
            for unit in self.units:
                area = self.enemy_area if (unit.group == "BLUE" and self.enemy_area is not None) \
                    else self.area
                point = geometry.Point(unit.coords[0:2])
                is_in_area = area.contains(point)
                if not is_in_area:
                    if unit.isactive:
                        unit.kill()
                    print(f"{unit}不在设定区域内！")

        # 判断锁定次数（同时更新命中计数）
        black_locked_num = 0
        white_locked_num = 0
        for unit in self.units_all:
            if unit.group == "BLUE" and isinstance(unit, Ship):
                black_locked_num += unit.locker.locked_times
            elif unit.group == "RED" and isinstance(unit, Ship):
                white_locked_num += unit.locker.locked_times

        # 检测新增的命中次数
        if black_locked_num > self.black_locked_num:
            self.cumulative_score["black_hit"] += (black_locked_num - self.black_locked_num)
        if white_locked_num > self.white_locked_num:
            self.cumulative_score["white_hit"] += (white_locked_num - self.white_locked_num)

        if black_locked_num >= self.black_locked_num and white_locked_num >= self.white_locked_num:
            self.black_locked_num = black_locked_num
            self.white_locked_num = white_locked_num
        else:
            raise RuntimeError(f"锁定次数少于上次锁定次数！"
                               f"黑方上轮次锁定次数{self.black_locked_num}, 本轮次锁定次数{black_locked_num};"
                               f"白方上轮次锁定次数{self.white_locked_num}, 本轮次锁定次数{white_locked_num}")



    def _send_event(self, dst, content, delay=0):
        assert content.__class__.__name__[:5] == "Event"
        body = cmsg.Event(self, dst, self.engine.time, content)
        self._notify(dst, body, delay=None, delay_ms=int(delay * 1000))
        self.engine.events.append(body)

    def implement(self):
        self._add_state("WORK", self._judge, repeat=self.attr.period, right_now=True)
        self._add_state("DEAD", lambda: None, repeat_ms=0)
        self._add_transfer("UNIFINED", "WORK", lambda: True)