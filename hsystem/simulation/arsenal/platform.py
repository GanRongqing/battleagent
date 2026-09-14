import collections
import random
from functools import partial
import numpy as np
import time

from .. import algorithm as alg
from .. import core
from .. import arsenal as asn
from .. import message as message
from .. import render as rdr
from simulation.core import CLASS, special_effect


class ShipAndSubmarine(core.arch.Platform):
    """
    """
    def _sonic_wave_handler(self, event):
        """
        """
        is_echo = False # 是否生成回波
        sonic_wave = event.content
        sonar = sonic_wave.source
        self.engine.log_info("ReceiveWave From %s To %s", sonar, self)
        if not sonar.is_in_angles(sonic_wave):
            return is_echo # 无回波
        area = sonar.which_area(sonic_wave)
        if area is None:
            return is_echo # 无回波
        if sonar.is_on and sonar.mode in ["active", "multi_active"]:
            echo_wave = message.event.EventSonicEcho(sonic_wave, area, self.engine.tick, None)
            res = sonar._echo_handle(echo_wave, advanced=True)
            if res:
                echo_wave = message.event.EventSonicEcho(sonic_wave, area, self.engine.tick, True)
                dis = alg.geo.distance(sonar.coords, self.coords)
                delay = dis / self.engine.env.sonic_speed
                self._send_event(sonar, echo_wave, delay=delay)
                self.engine.log_info("SendEcho From %s To %s", self, sonar)
                az = alg.geo.azimuth(self.coords, sonar.coords)
                if self.engine.render_config["sonar_wave"]:
                    core.special_effect.SonicWaveEffect.gen(self.engine, self.name, delay, az-5, az+5, sonar.unit.name)
                    # effect = core.special_effect.SonicWaveEffect(self, delay, az-5, az+5, dst=sonar)
                is_echo = True
        if sonar.mode == "multi_active":
            for co_sonar in sonar.co_sonars:
                if co_sonar.is_on and co_sonar.mode == "multi_passive":
                    echo_wave = message.event.EventSonicEcho(sonic_wave, area, self.engine.tick, None)
                    res = co_sonar._echo_handle(echo_wave, advanced=True)
                    if res:
                        echo_wave = message.event.EventSonicEcho(sonic_wave, area, self.engine.tick, True)
                        dis1 = alg.geo.distance(sonic_wave.s_coords, self.coords)
                        dis2 = alg.geo.distance(co_sonar.coords, self.coords)
                        if dis1 + dis2 > 2 * sonar.active_dis_max:
                            continue
                        delay = dis2 / self.engine.env.sonic_speed
                        self._send_event(co_sonar, echo_wave, delay=delay)
                        az = alg.geo.azimuth(self.coords, co_sonar.coords)
                        if self.engine.render_config["sonar_wave"]:
                            core.special_effect.SonicWaveEffect.gen(self.engine, self.name, delay, az-5, az+5, co_sonar.unit.name)
                            # effect = core.special_effect.SonicWaveEffect(self, delay, az-5, az+5, dst=co_sonar)
                        is_echo = True
        if is_echo:
            core.special_effect.HighlightEffect.gen(self.engine, self.name) # 增加高亮效果
        return is_echo

    def implement(self):
        super().implement()
        self._add_handler("EventSonicWave", self._sonic_wave_handler)


class Ship(ShipAndSubmarine):
    ## 平台挂载的加载顺序很重要
    single_attrs = ["characteristics", "vitalities", "comdev", "motor", "intelligence", "locker"]
    multi_attrs = ["radars", "sonars", "jammers", "other_sensors", "emitters", "guiders", "weaponsystems"]
    def __init__(self, engine, name, model, group, ptype=None, country=None):
        super().__init__(engine, name, model, group, ptype, country)
        self.planes = []
        self.add_child(self.locker)
        self.is_on = False

    @property
    def heading(self):
        # import pdb; pdb.set_trace()
        if self.motor.is_back:
            return (self.course+180)%360
        else:
            return self.course

    def load_uav(self, uav_name):
        if self.planes:
            return False
        else:
            self.planes.append(uav_name)
            return True

    def check(self):
        super().check()
        # assert isinstance(self.motor, ShipMotor)
        # import pdb; pdb.set_trace()
        assert hasattr(self.motor, "is_back")

    def draw(self, ax):
        super().draw(ax)
        x, y, _ = self.coords
        ax.scatter(x, y, c=self.group, marker=alg.marker.IconMarker("Ship", self.heading), s=200)
        if self.engine.render_config["name"]:
            ax.text(x, y, self.name, fontsize=9)
        if self.engine.render_config["ship_shape"]:
            rect = alg.shape.horizontal_rect3d_coords(self.heading+90, self.coords, self.characteristics.length, self.characteristics.width)
            ax.fill(rect[:,0], rect[:,1], c=self.group, alpha=0.5)

    def drawXz(self, ax):
        super().drawXz(ax)
        x, _, z = self.coords
        ax.scatter(x, z, c=self.group, marker="D", s=100)
        if self.engine.render_config["name"]:
            ax.text(x, z, self.name, fontsize=9)

    def draw3D(self, ax):
        super().draw3D(ax)
        x, y, z = self.coords
        ax.scatter(x, y, z, c=self.group, marker="D")
        if self.engine.render_config["name"]:
            ax.text(x, y, z, self.name, fontsize=6)
 
    def drawSymbol3D(self):
        items = super().drawSymbol3D()
        symbol3d = alg.shape.Symbol3D()
        symbol3d["id"] = str(id(self))
        symbol3d["mode"] = "Flag"
        symbol3d["type_"] = "Ship"
        symbol3d["model"] = self.model
        symbol3d["name"] = self.name
        symbol3d["group"] = self.group
        symbol3d["x"] = self.coords[0]
        symbol3d["y"] = self.coords[1]
        symbol3d["z"] = self.coords[2]
        symbol3d["az"] = self.heading
        symbol3d["color"] = self.group
        items.append(symbol3d)
        return items


class ShipCharacteristics(core.arch.Characteristics):
    def __init__(self, unit, model):
        super().__init__(unit, model)
        self.slope = np.sqrt(self.width**2+self.length**2)

    def get_rcs_and_line(self, seeker_coords):
        x1, y1, x2, y2 = alg.detection.ship_line(seeker_coords, self.unit.coords, 
                    self.unit.heading, self.length, self.width)
        line_length = np.linalg.norm([x2-x1, y2-y1])
        rcs = self.rcs*line_length/self.slope
        return rcs, (x1, y1, x2, y2)

    def get_RI_and_line(self, seeker_coords):
        x1, y1, x2, y2 = alg.detection.ship_line(seeker_coords, self.unit.coords, 
                    self.unit.heading, self.length, self.width)
        line_length = np.linalg.norm([x2-x1, y2-y1])
        RI = self.RI*line_length/self.slope
        return RI, (x1, y1, x2, y2)


class Submarine(ShipAndSubmarine):
    '''潜艇Unit0.
    '''
    def assemble(self):
        super().assemble()

    def draw(self, ax):
        super().draw(ax)
        x, y, _ = self.coords
        ax.scatter(x, y, c=self.group, marker=alg.marker.IconMarker("Submarine", self.course), s=150)
        if self.engine.render_config["name"]:
            ax.text(x, y, self.name, fontsize=9)

    def drawXz(self, ax):
        super().drawXz(ax)
        x, _, z = self.coords
        ax.scatter(x, z, c=self.group, marker="D", s=100)
        if self.engine.render_config["name"]:
            ax.text(x, z, self.name, fontsize=9)

    def draw3D(self, ax):
        super().draw3D(ax)
        x, y, z = self.coords
        ax.scatter(x, y, z, c=self.group, marker="^")
        if self.engine.render_config["name"]:
            ax.text(x, y, z, self.name, fontsize=6)

    def drawSymbol3D(self):
        items = super().drawSymbol3D()
        # symbol = alg.shape.Symbol(mode="Flag", type_="Submarine", group=self.group, name=self.name,
        #             x=self.coords[0],y=self.coords[1],az=self.course)
        # items.append(symbol)
        return items

class Plane(core.arch.Platform):
    """飞机
    """
    single_attrs = ["characteristics", "vitalities", "comdev", "motor", "intelligence", "commander", "driver", "mount", "missionsystem", "uavbattery"]
    multi_attrs = ["radars", "sonars", "jammers", "other_sensors", "emitters", "guiders", "weaponsystems", ]
    
    def __init__(self, engine, name, model, group, ptype=None, country=None):
        super().__init__(engine, name, model, group, ptype, country)
        self.be_able_intercepted = True
        self.set_motivate_param_num = 0
        self._return_to_base_cmd_name = None
        self.take_off_time = -1
        self.add_child(self.uavbattery)
        self.ship_home = None

    def take_off(self, uav_name, home_name, target_speed, target_course):
        _home = self.engine.unit_by_name(home_name)
        if uav_name in _home.planes:
            self.isdetectable = True
            self.charging = False
            # self.motor.set_motivate_param(self.coords, self.velocity)
            self.is_at_home = False
            self.motor.remove_home()
            self.radars[0].plat_at_home = False
            if not self.radars[0].is_on:
                self.radars[0].turn_on()
            self.motor.set_target_angle(target_course)
            self.motor.set_target_speed(target_speed)
            # self.motor._set_waypoints([self.coords + [0, 0, 100]], speed = 30)
            self.take_off_time = self.engine.time
            _home.planes = []
            self.ship_home = None
            return True
        else:
            return False

    def land(self, home_name):
        _home = self.engine.unit_by_name(home_name)
        if not _home.planes:
            _home.planes.append(self.name)
            self.ship_home = home_name
            self.motor.set_at_home(home_name)
            self.radars[0].plat_at_home = True
            self.radars[0].turn_off()
            self.is_at_home = True
            self.home_unit = _home
            return True
        else:
            return False

    def return_to_base(self, unit, cmd_name:str=None):
        self.home_unit = unit
        self.motor.insert_maneuver_cmd(cmd={"mode":"ReturnToBase"})
        self._return_to_base_cmd_name = cmd_name

    def _takeoff_handler(self, event):
        self._send_event(self.home_unit.airportsystem, event.content)
        flag = event.flag
        if flag == "Failure":
            self.kill()
            self.engine.log_physics("TakeOff Failure%r %r", self, self.home_unit)
        else:
            self.engine.log_physics("TakeOff %r %r", self, self.home_unit)

    def _landon_handler(self, event):
        flag = event.flag
        if flag == "Failure":
            self.kill()
            self.engine.log_physics("LandOn Failure%r %r", self, self.home_unit)
            cmd = self.engine.cmd_collections[self._return_to_base_cmd_name]
            cmd.end_time = self.engine.tick/1000
            cmd.res = "失败"
        else:
            if self._return_to_base_cmd_name:
                cmd = self.engine.cmd_collections[self._return_to_base_cmd_name]
                cmd.end_time = self.engine.tick/1000
                cmd.res = "成功"
                self._return_to_base_cmd_name = None
            for radar in self.radars:
                if radar.is_on:
                    radar._turn_off(None)
            if self.missionsystem:
                self.missionsystem._change_state("FREE")
            self.isdetectable = False
            self.is_at_home = True
            self.motor.set_ref_unit(self.home_unit)
            self.engine.log_physics("LandOn %r %r", self, self.home_unit)
        self._send_event(self.home_unit.airportsystem, event.content)


    def check(self):
        super().check()
        if self.commander:
            self.engine.log_warning(f"{self.name}建议使用missionsystem,不使用commander")
        if self.emitters:
            self.engine.log_warning(f"{self.name}建议使用mount,不使用emitter")
        if self.weaponsystems:
            self.engine.log_warning(f"{self.name}建议使用missionsystem,不使用weaponsystem")

    def implement(self):
        super().implement()
        self._add_handler("EventTakeOff", self._takeoff_handler)
        self._add_handler("EventLandOn", self._landon_handler)

    def draw(self, ax):
        super().draw(ax)
        if not self.is_at_home:
            x, y, _ = self.coords
            ax.scatter(x, y, c=self.group, marker=alg.marker.IconMarker("Plane", self.course), s=120)
            if self.engine.render_config["name"]:
                ax.text(x, y, self.name, fontsize=9)

    def drawXz(self, ax):
        super().drawXz(ax)
        if not self.is_at_home:
            x, _, z = self.coords
            ax.scatter(x, z, c=self.group, marker="D", s=100)
            if self.engine.render_config["name"]:
                ax.text(x, z, self.name, fontsize=9)

    def draw3D(self, ax):
        super().draw3D(ax)
        if not self.is_at_home:
            x, y, z = self.coords
            ax.scatter(x, y, z, c=self.group, marker="*")
            if self.engine.render_config["name"]:
                ax.text(x, y, z, self.name, fontsize=6)


class FixedWingPlane(Plane):
    """  """
    pass


class Helicopter(Plane):
    """  """
    pass


class Base(core.arch.FixedPlatform):
    """
    """
    def draw(self, ax):
        super().draw(ax)
        x, y, _ = self.coords
        ax.scatter(x, y, c=self.group, marker=alg.marker.IconMarker("Base", self.course), s=150)
        if self.engine.render_config["name"]:
            ax.text(x, y, self.name, fontsize=6)

    def drawXz(self, ax):
        super().drawXz(ax)
        x, _, z = self.coords
        ax.scatter(x, z, c=self.group, marker="D", s=150)
        if self.engine.render_config["name"]:
            ax.text(x, z, self.name, fontsize=6)

    def draw3D(self, ax):
        super().draw3D(ax)
        x, y, z = self.coords
        ax.scatter(x, y, z, c=self.group, marker="D")
        if self.engine.render_config["name"]:
            ax.text(x, y, z, self.name, fontsize=6)


class Airport(core.arch.FixedPlatform):
    """ 陆上机场 """
    single_attrs = ["characteristics", "vitalities", "comdev", "motor", "intelligence", "commander", "airportsystem"]
    multi_attrs = ["radars", "sonars", "jammers", "other_sensors", "emitters", "guiders", "weaponsystems"]

class SSMissileBase(core.arch.FixedPlatform):
    single_attrs = ["characteristics", "vitalities", "comdev", "motor", "intelligence", "commander", "airportsystem"]
    multi_attrs = ["radars", "sonars", "jammers", "other_sensors", "emitters", "guiders", "weaponsystems"]

class FixedFacility(core.arch.FixedPlatform):
    """ 预制固定设施平台
    """
    single_attrs = ["characteristics", "vitalities", "comdev", "motor", "intelligence"]
    multi_attrs = ["radars", "sonars"]
    
    def draw(self, ax):
        super().draw(ax)
        x, y, _ = self.coords
        ax.scatter(x, y, c=self.group, marker=alg.marker.IconMarker("Base", self.course), s=150)
        if self.engine.render_config["name"]:
            ax.text(x, y, self.name, fontsize=6)

    def drawXz(self, ax):
        super().drawXz(ax)
        x, _, z = self.coords
        ax.scatter(x, z, c=self.group, marker="D", s=150)
        if self.engine.render_config["name"]:
            ax.text(x, z, self.name, fontsize=6)

    def draw3D(self, ax):
        super().draw3D(ax)
        x, y, z = self.coords
        ax.scatter(x, y, z, c=self.group, marker="D")
        if self.engine.render_config["name"]:
            ax.text(x, y, z, self.name, fontsize=6)


class WaveEnergy(core.arch.Platform):
    pass

class UnderwaterCombatPlatform(core.arch.Platform):
    '''
    '''
    def draw(self, ax):
        super().draw(ax)
        x, y, _ = self.coords
        ax.scatter(x, y, c=self.group, marker=alg.marker.IconMarker("Base", self.course), s=150)
        if self.engine.render_config["name"]:
            ax.text(x, y, self.name, fontsize=6)

    def drawXz(self, ax):
        super().drawXz(ax)
        x, _, z = self.coords
        ax.scatter(x, z, c=self.group, marker="D", s=150)
        if self.engine.render_config["name"]:
            ax.text(x, z, self.name, fontsize=6)

    def draw3D(self, ax):
        super().draw3D(ax)
        x, y, z = self.coords
        ax.scatter(x, y, z, c=self.group, marker="D")
        if self.engine.render_config["name"]:
            ax.text(x, y, z, self.name, fontsize=6)


class LatentTarget(core.arch.Platform):
    """ 潜标
    """
    single_attrs = ["characteristics", "vitalities", "comdev", "motor", "intelligence"]
    multi_attrs = ["radars", "sonars"]

    def draw(self, ax):
        super().draw(ax)
        x, y, _ = self.coords
        ax.scatter(x, y, c=self.group, marker=alg.marker.IconMarker("Base", self.course), s=150)
        if self.engine.render_config["name"]:
            ax.text(x, y, self.name, fontsize=6)

    def drawXz(self, ax):
        super().drawXz(ax)
        x, _, z = self.coords
        ax.scatter(x, z, c=self.group, marker="D", s=150)
        if self.engine.render_config["name"]:
            ax.text(x, z, self.name, fontsize=6)


    def draw3D(self, ax):
        super().draw3D(ax)
        x, y, z = self.coords
        ax.scatter(x, y, z, c=self.group, marker="D")
        if self.engine.render_config["name"]:
            ax.text(x, y, z, self.name, fontsize=6)


class DriftingBuoy(core.arch.Platform):
    """ 漂流标
    """
    single_attrs = ["characteristics", "vitalities", "comdev", "motor", "intelligence"]
    multi_attrs = ["radars", "sonars"]

    def draw(self, ax):
        super().draw(ax)
        x, y, _ = self.coords
        ax.scatter(x, y, c=self.group, marker=alg.marker.IconMarker("Base", self.course), s=150)
        if self.engine.render_config["name"]:
            ax.text(x, y, self.name, fontsize=6)

    def drawXz(self, ax):
        super().drawXz(ax)
        x, _, z = self.coords
        ax.scatter(x, z, c=self.group, marker="D", s=150)
        if self.engine.render_config["name"]:
            ax.text(x, z, self.name, fontsize=6)

    def draw3D(self, ax):
        super().draw3D(ax)
        x, y, z = self.coords
        ax.scatter(x, y, z, c=self.group, marker="D")
        if self.engine.render_config["name"]:
            ax.text(x, y, z, self.name, fontsize=6)