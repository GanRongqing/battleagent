import time
import random
import numpy as np
from matplotlib.patches import Circle
from matplotlib.collections import PatchCollection

from .. import algorithm as alg
from .. import core
from .. import message
from .. import arsenal as asn


class Locker(core.arch.Component):
    '''锁定仿真模块'''

    def __init__(self, unit, model):
        super().__init__(unit, model)
        self._is_on = False
        self.locked = False
        self.locked_begin_time = None
        self.locked_end_time = None
        self.locked_times = 0
        self.frozen = False
        self.emy_name = None
        self.frozen_time = None
        self.locking_name = None
        self.locking = False

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
        assert not self._is_on
        self._is_on = True

    def _turn_off(self):
        """关机"""
        assert self._is_on
        self._is_on = False

    def is_locking(self, p):
        ## 确保每个船只能锁定一个目标
        if not self.locking:
            self.locking = True
            self.locking_name = p
            return True
        else:
            return False

    def dis_lock(self):
        self.locking = False
        self.locking_name = None

    def is_locked(self, unit_name):
        ## 判断unit_name，确保每个船只能锁定一个目标
        print("from locker_old")
        _unit = self.engine.unit_by_name(unit_name)
        if _unit.locker.locking:
            print(f"{unit_name}正在锁定其它目标！")
            return False
        
        ## 锁定判断
        if not self.locked:
            self.locked = True
            self.locked_begin_time = self.engine.time
            self.emy_name = unit_name
            return True
            # special_effect.LinkEffect.gen(self.engine, unit_name, self.name)
        else:
            if self.emy_name != unit_name:
                ## 更新锁定
                _emy = self.engine.unit_by_name(self.emy_name)
                _emy.locker.dis_lock()
                self.locked_begin_time = self.engine.time
                self.emy_name = unit_name
                return True
            else:
                ## 重复锁定视为执行失败
                print(f"{unit_name}在重复锁定{self.home_unit}！")
                return False

    def _locked_work(self):
        if self.locked_times >= 2:
            if len(self.home_unit.planes) > 0:
                _plane_name = self.home_unit.planes[0]
                _plane = self.engine.unit_by_name(_plane_name)
                _plane.kill()
            self.home_unit.kill()
        else:
            if self.frozen:
                ## 让船的Motor停止
                self.home_unit.motor.set_frozen()
                if self.home_unit.radars[0]._is_on:
                    self.home_unit.radars[0].turn_off()
                if self._is_on:
                    self._turn_off()
            else:
                if self.emy_name and self.locked and self.locked_begin_time:
                    locked_time = self.engine.time - self.locked_begin_time
                    if locked_time > 300 and random.random() > 0.2:
                        self.locked_times += 1
                        self.frozen = True
                        self.frozen_time = self.engine.time
                        self.locked = False
                    emy_unit = self.engine.unit_by_name(self.emy_name)
                    if alg.geo.distance(emy_unit.coords, self.coords) >= 40_000:
                        self.locked = False
                        self.locked_begin_time = None
                        self.emy_name = None
        if self.frozen_time:
            if self.engine.time - self.frozen_time > 300:
                self.frozen = False
                self.frozen_time = None
                self.locked = False
                self.locked_begin_time = None
                ## 让船的Motor重启
                self.home_unit.motor.frozen_release()
                if not self.home_unit.radars[0]._is_on:
                    self.home_unit.radars[0].turn_on()
                if not self._is_on:
                    self._turn_on()

    def _locking_work(self):
        if self.locking:
            locking_unit = self.engine.unit_by_name(self.locking_name)
            if not locking_unit:
                self.locking = False
                self.locking_name = None
            if alg.geo.distance(locking_unit.coords, self.coords) >= 40_000:
                self.locking = False
                self.locking_name = None
            if locking_unit.locker.frozen:
                self.locking = False
                self.locking_name = None
            # self.locking = locking_unit.locker.locked
        else:
            self.locking_name = None

    def _lock_work(self):
        self._locking_work()
        self._locked_work()

    def _draw(self, ax=None, mode="draw"):
        """
        mode = "draw" or "qt"
        """
        items = []
        if self.locking and self.locking_name:
            if self.is_on:
                locking_unit = self.engine.unit_by_name(self.locking_name)
                # 获取扇环角度信息
                course = alg.geo.azimuth(self.coords, locking_unit.coords)
                center = self.coords[:2]
                if self.attr.sector:
                    sector = alg.shape.Sector(center, self.attr.dis, self.attr.sector[0] + course, self.attr.sector[1] + course)
                else:
                    sector = alg.shape.Circle(center, self.attr.dis)
                if mode == "draw":
                    sector.fill(ax, c=self.group, alpha=0.1)
                else:
                    item = sector.fillSymbol(color=self.group,
                                             fill_color=self.group,
                                             fill_alpha=0.1)

                    items.append(item)
        if self.is_on:
            sector = alg.shape.Circle(self.coords[:2], self.attr.dis)
            if mode == "draw":
                sector.fill(ax, c=self.group, alpha=0.1)
            else:
                item = sector.fillSymbol(color=self.group, fill_color=self.group, alpha=0, fill_alpha=0.1)
                items.append(item)
        if mode != "draw":
            return items

    def implement(self):
        self._add_state("WORK", self._lock_work, self.attr.period)
        self._add_handler("CmdLockerTurnOn", self._turn_on)
        self._add_handler("CmdLockerTurnOff", self._turn_off)

    def draw(self, ax):
        self._draw(ax, mode="draw")

    def drawSymbol(self):
        return self._draw(ax=None, mode="symbol")