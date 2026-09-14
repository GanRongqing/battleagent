import numpy as np
import copy
import collections
import time

from .. import algorithm as alg
from .. import core
from .. import message
from .. import arsenal as asn
from .. import render as rdr


class UpperSensor(core.arch.Sensor):
    """
    """
    def __init__(self, unit, model):
        super().__init__(unit, model)
        if self.sector is None:
            if self.attr.has_attr("sector"):
                if self.attr.sector:
                    self.set_sector(self.attr.sector)
        self._prev_h = None

        self._redis_count_id = 0
        if self.unit.group.lower() == 'red':
            self.border_color = [255,0,0,255]
        elif self.unit.group.lower() == 'blue':
            self.border_color = [0,0,255,255]
        else:
            self.border_color = [100,100,100,255]

    def d1(self, foe=None, foe_params=None):
        """
        """
        if foe is not None:
            h = foe.coords[2]
        else:
            h = foe_params["height"]
        if h < 0:
            return 0
        Ha = self.coords[2] + self.attr.antenna_height
        dis, _ = alg.detection.detect_near_bound(h, Ha, self.attr.low_angle, self.attr.up_angle, self.engine.env.Rs)
        return dis

    def d2(self, foe=None, foe_params=None):
        """
        """
        if foe is not None:
            h = foe.coords[2]
        else:
            h = foe_params["height"]
        if h < 0:
            return 0
        Ha = self.coords[2] + self.attr.antenna_height
        dis, _= alg.detection.detect_far_bound(h, Ha, self.attr.low_angle, self.attr.max_distance, self.engine.env.Rs)
        return dis

    def update_draw_data(self):
        if not self.engine.sim_config["earth_curvature"]:
            return
        if (self._prev_h is not None) and abs(self.coords[2]-self._prev_h) <= 1:
            return
        self._prev_h = self.coords[2]

        N = 20 #采样点
        _h = np.linspace(0, self.attr.max_height, N).tolist()
        Ha = self.coords[2] + self.attr.antenna_height
        _d1 = [] #近界(空间距离)
        _x1 = [] #近界(水平距离)
        _d2 = [] #远界(空间距离)
        _x2 = [] #远界(空间距离)
        for h in _h:
            dd, pp = alg.detection.detect_near_bound(h, Ha, self.attr.low_angle, self.attr.up_angle, self.engine.env.Rs)
            _d1.append(dd)
            _x1.append(pp)
            dd, pp = alg.detection.detect_far_bound(h, Ha, self.attr.low_angle, self.attr.max_distance, self.engine.env.Rs)
            _d2.append(dd)
            _x2.append(pp)
        self._h = np.array(_h)
        self._d1 = np.array(_d1)
        self._d2 = np.array(_d2)
        self._x1 = np.array(_x1)
        self._x2 = np.array(_x2)
        self.X1, self.Y1, self.Z1 = alg.shape.rotate_by_z(self._x1, self._h) #绘制三维所需数据
        self.X2, self.Y2, self.Z2 = alg.shape.rotate_by_z(self._x2, self._h) #绘制三维所需数据

    def check(self):
        super().check()
        assert self.attr.has_attr("class")
        assert self.attr.has_attr("up_angle")
        assert self.attr.has_attr("low_angle")
        assert self.attr.has_attr("antenna_height")
        assert self.attr.has_attr("max_height")
        assert self.attr.has_attr("max_distance")


class MagneticDetector(core.arch.Sensor):
    """
    """

    def __init__(self, unit, model):
        super().__init__(unit, model)
        self._es = set() #

    def _detect(self):
        es = [e for e in self.engine.actives() if e.isactive and e.group != self.group]
        foes = [ e for e in es  if isinstance(e, asn.platform.Submarine)]
        # 探测
        radius = self.attr.radius
        period = self._state_period
        for e in foes:
            t = alg.geo.TCL(self.coords, radius*0.5, self.velocity, e.coords, radius*0.5, e.velocity)
            if 0 <= t <= period:
                track = message.track.MagneticDetectorTrack(e, self, self.engine.tick)
                if e not in self._es:
                    self._es.add(e)
                    self.engine.log_sensor("Found[%s] %r %r", track.mode, self, track.target)
                content = core.message.MsgTrack(track)
                for intel in self._processors:
                    self._send_msg(intel, content)

    def _turn_on(self, cmd):
        super()._turn_on(cmd)
        self._render()

    def check(self):
        self.attr.has_attr("radius")

    def _render(self):
        if self.isactive and self.is_on:
            if self.attr.radius > self.coords[2]:
                r = np.sqrt(self.attr.radius**2-self.coords[2]**2)
                core.special_effect.DynamicRangeEffect.update(self.engine, self.ucname, self.unit.name, r2=r, color=self.group.lower())
            else:
                core.special_effect.DynamicRangeEffect.kill(self.engine, self.ucname)
            self.engine.set_timer_triger(self._render, delay=self.engine.sim_interval()) # 每隔真实时间的1s更新一次
        else:
            core.special_effect.DynamicRangeEffect.kill(self.engine, self.ucname)

    def drawXz(self, ax):
        if self.is_on:
            if self.attr.radius > self.coords[2]:
                r = np.sqrt(self.attr.radius**2-self.coords[2]**2)
                az1 = np.rad2deg(np.arctan2(r,-self.coords[2]))
                az2 = 360 - az1
                sector = alg.shape.Sector(self.coords[[0,2]], self.attr.radius, az1, az2)
                sector.plot(ax, "-", c=self.group, linewidth=1)


class PhotoelectricSensor(UpperSensor):
    """
    """
    def __init__(self, unit, model):
        super().__init__(unit, model)
        self._found_target_tracks = {} # target:(first_track, now_track)

    @property
    def targets(self):
        return [target for target in self._found_target_tracks.keys() if target.isactive]

    @property
    def photoelectric_tracks(self):
        return set([tracks[1] for tracks in self._found_target_tracks.values()])

    def acquire(self, foe):
        if not self._is_on:
            return False

        # 判断高度是否满足条件
        if foe.coords[2] > self.attr.max_height or foe.coords[2] < 0:
            return False

        # 判断扇面角是否满足条件
        if self.sector is not None:
            az = alg.geo.azimuth(self.coords, foe.coords)
            sector = self.sector + self.unit.heading
            res = alg.geo.in_angle_range2(az, np.array(sector))
            if not res:
                return False

        # 判断距离是否满足条件
        dis = alg.geo.distance(self.coords, foe.coords)
        if dis > self.attr.max_distance:
            return False

        # 判断地球曲率
        if self.engine.sim_config["earth_curvature"]:
            if dis < self.d1(foe) or dis > self.d2(foe):
                return False

        # 判断地形
        if self.engine.sim_config["terrain_effect"]:
            if self.engine.env.terrain is not None:
                if not alg.detection.detect_max_distance(self.coords, self.attr.antenna_height, foe.coords,
                                                        self.engine.env.terrain.finterp):
                    return False

        # 探测判断
        if foe.model in self.attr.detect_dis:
            dis_detect = self.attr.detect_dis[foe.model]
        else:
            dis_detect = self.attr.detect_dis['normal']
        if dis > dis_detect:
            return False
        return True

    def _search(self):
        foes = [e for e in self.engine.actives() if e.isdetectable and e.group != self.group
                        and isinstance(e, (asn.platform.Ship, asn.platform.Plane, asn.missile_ss.SSMissile, asn.platform.Base))]
        seen = set(filter(self.acquire, foes))
        return seen

    def _detect(self):
        seen = self._search()
        found = set(self._found_target_tracks.keys())
        for m in seen:
            az = alg.geo.azimuth(self.coords, m.coords)
            pitch = alg.geo.pitch(self.coords, m.coords)
            track = message.track.PhotoelectricTrack(m, self, self.engine.tick, az=az, pitch=pitch)
            if m in self._found_target_tracks:
                self._found_target_tracks[m] = track
                self.engine.log_info("Found %r %s %s", self, track.target, "(%.3f,%0.3f)" % (track.az, track.pitch))
            else:
                self._found_target_tracks[m] = track
                self.engine.log_sensor("Found %r %s %s", self, track.target, "(%.3f,%0.3f)" % (track.az, track.pitch))

            content = core.message.MsgTrack(track)
            for processor in self._processors:
                self._send_msg(processor, content)

        # 去掉无效的目标
        rem = []
        for m in (found - seen):
            if not m.isactive:
                rem.append(m)
                continue
            m_track = self._found_target_tracks[m]
            if self.engine.tick - m_track.when <= 1000*self.attr["update_time"]:
                continue
            rem.append(m)
            self.engine.log_sensor("Lost %r %r", self, m)
        for m in rem:
            self._found_target_tracks.pop(m)

    def check(self):
        super().check()
        assert self.attr.has_attr("class")
        assert self.attr.has_attr("period")
        assert self.attr.has_attr("update_time")
        assert self.attr.update_time >= self.attr.period
        assert self.attr.has_attr("detect_dis")

    def _draw(self, ax=None, mode="draw"):
        items = []
        if self.is_on and self.state_time > 1:
            # 画探测范围
            # self.attr.update_interp()
            foe_params = self.engine.render_config["target"]
            h = foe_params["height"]
            if h > self.attr.max_height:
                return items
            center = self.coords[:2]

            if self.engine.sim_config["earth_curvature"]:
                d2 = self.d2(foe_params=foe_params)
            else:
                d2 = np.inf

            if self.engine.sim_config["terrain_effect"]:
                ## szs, 增加地形遮蔽的计算
                pass

            radius = min(d2, self.attr.detect_dis["normal"]) # 未考虑干扰的影响
            tag = f"[{h}m]"


            if self.sector is None:
                shp = alg.shape.Circle(center, radius)
            else:
                az1, az2 = self.sector + self.unit.heading
                shp = alg.shape.Sector(center, radius, az1, az2)

            x, y = shp.exterior.xy
            if mode == "draw":
                shp.plot(ax, c=self.group, linewidth=1)
            elif mode == "symbol":
                symbol = shp.fillSymbol(type_="Radar", group=self.group, color=self.group)

            if mode == "symbol":
                return [symbol]

            # 画标识 
            if self.engine.render_config["name"]:
                ax.text(x[0], y[0], f"{self.name}"+tag, fontsize=6)

            # 画探测到的目标
            found = set(self._found_target_tracks.keys())
            for t in found:
                x, y, z = t.coords
                ax.scatter(x, y, marker="*", c=t.group.lower(), s=20)

    def draw(self, ax):
        self._draw(ax=ax, mode="draw")

    def turn_on(self):
        super().turn_on()
        r = self.attr.detect_dis['normal']
        self._redis_count_id += 1
        entity_id = self.engine.render_data[self.unit.name].entity_id
        range_id = str(self.id)+"_electric_" + str(self._redis_count_id)
        event1 = {'time': time.time(), 'target_type': 'range', "event_type": "create",
                    'event_property': {"range_type": "circle", "range_id": range_id, "location": self.coords.tolist(),
                                    "radius": r, "border_color": self.border_color, "entity_id": entity_id,
                                    "inner_radius": 0, "fill_color": [0,0,0,0], "time": self.engine.ymdhms}}
        self.engine.push_render_event(event1)

    def turn_off(self):
        super().turn_off()
        # 隐藏或销毁
        range_id = str(self.id)+"_electric_" + str(self._redis_count_id)
        event1 = {'time': time.time(), 'target_type': 'range', "event_type": "destroy",
                 'event_property': {"range_id": range_id, "time": self.engine.ymdhms}}
        self.engine.push_render_event(event1)

