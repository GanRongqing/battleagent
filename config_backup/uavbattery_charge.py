import time
import random
import numpy as np
from matplotlib.patches import Circle
from matplotlib.collections import PatchCollection

from .. import algorithm as alg
from .. import core
from .. import message
from .. import arsenal as asn


class UavBattery(core.arch.Component):
    '''无人机补能仿真模块'''
    def __init__(self, unit, model):
        super().__init__(unit, model)
        self._is_on = False
        self.take_off_time = -1  # 飞机的起飞时间
        # 从数据库读取总飞行时间和充电时间, 默认2小时飞行/5小时充电
        try:
            self.total_fly_time = self.attr.total_fly_time
        except Exception:
            self.total_fly_time = 2 * 60 * 60
        try:
            self.total_charge_time = self.attr.total_charge_time
        except Exception:
            self.total_charge_time = 5 * 60 * 60
        # 充电速率(每秒恢复的飞行秒数) = 总飞行时间/总充电时间
        self.charge_rate = self.total_fly_time / self.total_charge_time if self.total_charge_time > 0 else 0.4
        self.fly_time_remain = self.total_fly_time
        self.charging = False
        self.charge_time = 0

    @property
    def is_on(self):
        return self._is_on

    def turn_on(self):
        """开机"""
        assert not self._is_on
        self._is_on = True
        self._change_state("WORK")  # 立即进入工作状态

    def turn_off(self):
        """关机"""
        assert self._is_on
        self._is_on = False
        self._change_state("FREE")  # 立即进入空闲状态

    def _turn_on(self):
        """开机"""
        self.turn_on()

    def _turn_off(self):
        """关机"""
        self.turn_off()

    def charge(self):
        if not self.charging:
            assert self.home_unit.is_at_home
            self.charging = True
            self.charge_time = self.engine.time
            return True
        else:
            return False

    def _battery_work(self):
        if not self.home_unit.is_at_home:
            self.charging = False
            self.fly_time_remain = self.total_fly_time - (self.engine.time - self.home_unit.take_off_time)
            if self.fly_time_remain < 0:
                self.home_unit.kill()
        if self.home_unit.is_at_home and (self.fly_time_remain < self.total_fly_time):
            self.charge()
            # 充电速率按比例恢复
            self.fly_time_remain = self.fly_time_remain + self.charge_rate * self.attr.period
            if self.fly_time_remain >= self.total_fly_time:
                self.charging = False
                self.fly_time_remain = self.total_fly_time

    def _draw(self, ax=None, mode="draw"):
        """
        mode = "draw" or "qt"
        """
        items = []
        if self.is_on:
            center = self.home_unit.coords[:2]
            sector = alg.shape.Sector(center, 10000, 0, max(max(self.fly_time_remain, 0)/self.total_fly_time*360, 4))
            if mode == "draw":
                sector.fill(ax, c='Green', alpha=0.1)
            else:
                item = sector.fillSymbol(color='Green', fill_color='Green', fill_alpha=0.1)
                items.append(item)
        if mode != "draw":
            return items

    def implement(self):
        self._add_state("WORK", self._battery_work, self.attr.period)

    def draw(self, ax):
        self._draw(ax, mode="draw")

    def drawSymbol(self):
        return self._draw(ax=None, mode="symbol")