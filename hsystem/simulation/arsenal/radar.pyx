import time
import numpy as np
from shapely import geometry
from scipy.interpolate import interp1d
from simulation.algorithm.geometry import pitch
from simulation.core.enums import LogCommandLabel
from collections import defaultdict

from .. import algorithm as alg
from ..core.arch cimport Sensor
from ..core import message as cmsg
from ..core import special_effect, CLASS
from .. import message
from ..arsenal import platform

cdef class Radar(Sensor):
    """ 通用雷达组件
    """
    def __init__(self, unit, model):
        super().__init__(unit, model)
        self._fake_find_pro = None
        self._A0 = None
        self._coef = None
        if self.attr.detected_method in ["formula", "prob"]:
            _distance = float(self.attr["base_foe"]["distance"]) # 雷达探测距离
            _find_pro = self.attr["base_foe"]["find_pro"] # 发现概率
            self._fake_find_pro = self.attr["base_foe"]["fake_find_pro"]  # 虚警概率
            _rcs = self.attr["base_foe"]["rcs"] # 目标rcs
            self._A0 = alg.detection.detect_A0(_distance, self._fake_find_pro, _find_pro, _rcs)
        elif self.attr.detected_method == "fixed":
            # import pdb;pdb.set_trace()
            try:
                _distance = float(self.attr["base_foe2"]["distance"]) # 雷达探测距离
            except:
                import pdb;pdb.set_trace()
            _rcs = self.attr["base_foe2"]["rcs"] # 目标rcs
            self._coef = alg.detection.detect_coef(_distance, _rcs)
        
        self._dis_formula = {} # 
        self._dis_sigma = {}
        self._prev_h = None

        if self.sector is None:
            if self.attr.has_attr("sector"):
                if self.attr.sector:
                    self.set_sector(self.attr.sector)

        self._found_target_tracks = {}
        self._jammers = {}
        self._found_with_log_track = set()

        self._redis_count_id = 0
        if self.unit.group.lower() == 'red':
            self.border_color = [255,0,0,255]
        elif self.unit.group.lower() == 'blue':
            self.border_color = [0,0,255,255]
        else:
            self.border_color = [100,100,100,255]

    property targets:
        def __get__(self):
            return [target for target in self._found_target_tracks.keys() if target.isactive]

    property radar_tracks:
        def __get__(self):
            return set([tracks[1] for tracks in self._found_target_tracks.values()])

    property jammed_coef:
        def __get__(self):
            jammed_coef = 1
            if self._jammers:
                for _ in self._jammers:
                    jammed_coef *= 0.8
            return jammed_coef
    
    cpdef set_sector(self, list sector):
         #若探测扇面角设置为0-360，那么直接设置为空，效果一样，避免bug
        if sector == [0, 360]:
            self._sector = None
        else:
            self._sector = np.array(sector, dtype=np.float64)

    cpdef bint acquire(self, foe):
        """ 雷达(含照射器)能否探测到该目标
        """
        if not self.isactive:
            return False

        if not self._is_on:
            return False
        
        cdef double [:] self_coords_mv = self.coords
        cdef double [:] foe_coords_mv = foe.coords

        # 判断高度是否满足条件
        if foe_coords_mv[2] > self.attr.max_height or foe_coords_mv[2] < 0:
            return False

        # 判断扇面角是否满足条件
        if self.sector is not None:
            az = alg.geo.azimuth(self.coords, foe.coords)
            sector = self.sector + self.unit.heading
            res = alg.geo.in_angle_range2(az, np.array(sector))
            if not res:
                return False

        # 判断距离是否满足条件
        cdef double dis = ((foe_coords_mv[0]-self_coords_mv[0])**2 + (foe_coords_mv[1]-self_coords_mv[1])**2 + (foe_coords_mv[2]-self_coords_mv[2])**2)**0.5
        if dis > self.attr.max_distance:
            return False

        # 固定模式
        if self.attr.detected_method == "fixed":
            if dis < self.attr.distance:
                return True
            else:
                return False
        # 概率探测模式
        elif self.attr.detected_method == "prob":
            # dis = alg.geo.distance(foe.coords, self.coords)
            if dis > self._cal_jam_dis_by_formula(foe=foe, jammed_coef=self.jammed_coef):  # 干扰削弱探测距离
                return False
            return True
        # 公式探测模式
        elif self.attr.detected_method == "formula":
            if foe not in self._found_target_tracks:
                if np.random.random() >= self._cal_pro_by_formula(foe) * self.jammed_coef:  # 干扰削弱探测概率
                    return False
            return True
        else:
            raise RuntimeError("unknown detected method")  

    cpdef float _cal_near_dis(self, foe=None, dict foe_params=None):
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

    cpdef float _cal_far_dis(self, foe=None, dict foe_params=None):
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

    cpdef float _cal_dis_by_formula(self, foe=None, dict foe_params=None):
        if foe is not None:
            rcs = foe.characteristics.rcs
        else:
            rcs = foe_params["rcs"]
        # 惰性求值
        if rcs in self._dis_formula:
            return self._dis_formula[rcs]
        prob = self.attr.prob
        d = alg.detection.detect_d_by_prob(prob, self._fake_find_pro, self._A0, rcs)
        self._dis_formula[rcs] = d
        return d

    cpdef float _cal_dis_by_coef(self, foe=None, dict foe_params=None):
        if foe is not None:
            rcs = foe.characteristics.rcs
        else:
            rcs = foe_params["rcs"]
        # 惰性求值
        if rcs in self._dis_sigma:
            return self._dis_sigma[rcs]
        d = alg.detection.detect_d_by_coef(self._coef, rcs)
        self._dis_sigma[rcs] = d
        return d

    cpdef float _cal_jam_dis_by_formula(self, foe=None, dict foe_params=None, float jammed_coef=1):
        if foe is not None:
            rcs = foe.characteristics.rcs
        else:
            rcs = foe_params["rcs"]
        # 惰性求值
        if rcs in self._dis_formula:
            return self._dis_formula[rcs]
        prob = self.prob * jammed_coef
        d = alg.detection.detect_d_by_prob(prob, self._fake_find_pro, self._A0, rcs)
        self._dis_formula[rcs] = d
        return d

    cpdef float _cal_pro_by_formula(self, foe):
        d = alg.geo.distance(self.coords, foe.coords)
        pp = alg.detection.detect_prob(d, self._fake_find_pro, self._A0, foe.characteristics.rcs)
        return pp

    cpdef float _cal_jam_dis_fixed(self, az_foe, pitch_foe, foe):
        if foe.model in self.attr.fixed_dis:
            dis_fixed = self.attr.fixed_dis[foe.model]
        else:
            # dis_fixed = self.attr.fixed_dis['normal'] # 不再使用normal, 使用简化公式计算如下:
            dis_fixed = self._cal_dis_by_coef(foe=foe)
        min_dis = dis_fixed
        for jammer in self._jammers.keys():
            az_jammer = alg.geo.azimuth(self.coords, jammer.coords)
            pitch_jammer = alg.geo.pitch(self.coords, jammer.coords)
            if abs(alg.geo.angle_diff(az_foe, az_jammer)) >= jammer.attr.beta:
                continue
            if abs(alg.geo.angle_diff(pitch_foe, pitch_jammer)) >= jammer.attr.alpha:
                continue
            # 目标在干扰机的干扰作用范围内
            if jammer.attr.disturb_method == "disturb_coef":
                min_dis = min(min_dis, dis_fixed*jammer.attr.desturb_coef)
            elif jammer.attr.disturb_method == "disturb_dis":
                min_dis = min(min_dis, jammer.attr.disturb_dis)
        return min_dis

    cpdef _update_interp(self):
        if not self.engine.sim_config["earth_curvature"]:
            return
        if (self._prev_h is not None) and abs(self.coords[2]-self._prev_h) <= 1:
            return
        self._prev_h = self.coords[2]
        cdef int N = 20 #采样点
        cdef list _h = np.linspace(0, self.attr.max_height, N).tolist()
        cdef float Ha = self.coords[2] + self.attr.antenna_height
        cdef list _d1 = [] #近界(空间距离)
        cdef list _x1 = [] #近界(水平距离)
        cdef list _d2 = [] #远界(空间距离)
        cdef list _x2 = [] #远界(空间距离)
        cdef float h
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
        # 因插值方法对低空目标的误差很大，因此去掉插值方法
        # self._d1_interp = interp1d(self._h, self._d1, kind="linear")
        # self._d2_interp = interp1d(self._h, self._d2, kind="linear")
        self.X1, self.Y1, self.Z1 = alg.shape.rotate_by_z(self._x1, self._h) #绘制三维所需数据
        self.X2, self.Y2, self.Z2 = alg.shape.rotate_by_z(self._x2, self._h) #绘制三维所需数据

    cpdef _update_jammers(self):
        for jammer in list(self._jammers.keys()):
            if (self.engine.tick - self._jammers[jammer])/1000.0 >= 2*jammer.attr.period:
                del (self._jammers[jammer])

    cpdef set _search(self):
        cdef list foes = [e for e in self.engine.actives() if e.isdetectable and e.group != self.group 
                        and isinstance(e, (platform.Ship, platform.Plane, platform.Base, platform.Submarine))]
        cdef set seen = set(filter(self.acquire, foes))

        for foe in seen:
            if not foe in self.engine.first_found_time_dict:
                self.engine.first_found_time_dict[foe.name] = self.engine.time
        return seen

    cpdef _detect(self):
        self._update_jammers()
        cdef set seen = self._search()
        cdef set found = set(self._found_target_tracks.keys())
        for m in seen:
            if m in self._found_target_tracks:
                first_track, _ = self._found_target_tracks[m]
                if self.engine.tick - first_track.when >= 1000*self.attr["yield_time"]:
                    flag = "track"
                else:
                    flag = "point"
                m_track = message.track.RadarTrack(m, self, self.engine.tick, "active", m.coords, m.velocity, flag=flag)
                self._found_target_tracks[m] = (first_track, m_track)
                if flag == "track":
                    if m not in self._found_with_log_track:
                        self.engine.log_sensor("Found[active][%s] %r %r", flag, self, m)
                        self._found_with_log_track.add(m)
                else:
                    self.engine.log_sensor("Found[active][%s] %r %r", flag, self, m)
            else:
                flag = "point"
                m_track = message.track.RadarTrack(m, self, self.engine.tick, "active", m.coords, m.velocity, flag=flag)
                self._found_target_tracks[m] = (m_track, m_track)
                self.engine.log_sensor("Found[active][%s] %r %r", flag, self, m)
                event = message.event.EventDetectFirst(m, self)
                # if self.unit.commander is not None:
                #     self._send_event(self.unit.commander, event)
            if flag == "track":
                content = cmsg.MsgTrack(m_track)
                for processor in self._processors:
                    self._send_msg(processor, content)
        # 去掉无效的目标
        cdef list rem = []
        for m in (found - seen):
            if not m.isactive:
                rem.append(m)
                continue
            first_track, m_track = self._found_target_tracks[m]
            if self.engine.tick - m_track.when <= 1000*self.attr["update_time"]:
                continue
            rem.append(m)
            self.engine.log_sensor("Lost %r %r", self, m)
        for m in rem:
            self._found_target_tracks.pop(m)

    cpdef turn_on(self):
        "开机"
        Sensor.turn_on(self)
        self._render()

    cpdef turn_off(self):
        self._found_target_tracks = {} # target:(first_track, now_track)
        self._jammers = {} # 受到干扰的干扰设备列表, jammer:tick
        Sensor.turn_off(self)

    cpdef kill(self):
        Sensor.kill(self)
        # 销毁指令

    cpdef _jam_radar_handler(self, event):
        # self._jammers.add(event.content.jammer)
        self._jammers[event.content.jammer] = self.engine.tick

    cpdef implement(self):
        Sensor.implement(self)
        self._add_handler("EventJamRadar", self._jam_radar_handler)

    cpdef check(self):
        Sensor.check(self)
        assert self.attr.has_attr("class")
        assert self.attr.has_attr("period")
        assert self.attr.has_attr("yield_time")
        assert self.attr.has_attr("update_time")
        assert self.attr.update_time >= self.attr.period
        assert self.attr.yield_time >= self.attr.update_time
        assert self.attr.has_attr("up_angle")
        assert self.attr.has_attr("low_angle")
        assert self.attr.up_angle >= 0, "radar up_angle must be > 0"
        assert self.attr.low_angle <= 0, "radar low_angle must be < 0"
        assert self.attr.has_attr("antenna_height")
        assert self.attr.has_attr("max_height")
        assert self.attr.has_attr("max_distance")
        assert self.attr.has_attr("detected_method")
        assert self.attr.detected_method in ["formula", "prob", "fixed"]
        if self.attr.detected_method == "fixed":
            assert self.attr.has_attr("fixed_dis")
            assert isinstance(self.attr.fixed_dis, dict)
            if "normal" in self.attr.fixed_dis:
                self.engine.log_warning("%s中的参数fixed_dis中的normal关键字已不再使用，建议去掉；同时增加base_foe2参数", self)
            assert self.attr.has_attr("base_foe2")
            assert isinstance(self.attr.base_foe2, dict)
        elif self.attr.detected_method == "prob":
            assert self.attr.has_attr("prob")
            assert self.attr.has_attr("base_foe")
            assert isinstance(self.attr.base_foe, dict)
            assert 0.0 < self.attr.prob < 1.0
        else:
            assert self.attr.has_attr("base_foe")
            assert isinstance(self.attr.base_foe, dict)

    cpdef _render_range_update(self):
        radius = self.attr.distance
        if self.sector is None:
            az1, az2 = 0, 360
        else:
            az1, az2 = (self.sector + self.unit.heading)
        if radius > 0:
            special_effect.DynamicRangeEffect.update(self.engine, self.ucname, self.unit.name, r2=radius,
                                                            az1=az1, az2=az2, color=self.group.lower())

    cpdef _render(self):
        """ 支持对web地图、庚图、白板的三种绘制模式 """
        if self.isactive and self.is_on:
            if self.engine.render_config["radar"]:
                self._render_range_update()
            else:
                special_effect.DynamicRangeEffect.kill(self.engine, self.ucname)
            self.engine.set_timer_triger(self._render, delay=self.engine.sim_interval()) # 每隔真实时间的1s更新一次
            # 不能使用self._next, 因当self.isactive为False，会忽略该信息而不执行
        else:
            special_effect.DynamicRangeEffect.kill(self.engine, self.ucname)

    cpdef list _draw(self, ax=None, str mode="draw"):
        items = []
        # 画探测到的目标
        if mode == "draw":
            found = set(self._found_target_tracks.keys())
            for t in found:
                x, y, z = t.coords
                ax.scatter(x, y, marker="*", c=t.group.lower(), s=20)
        return items

    cpdef drawXz(self, ax):
        if not self.engine.render_config["radar"]: return
        x0, y0, z0 = self.coords
        if self.is_on and self.state_time > 1:
            self._update_interp()
            # 画探测范围
            if (not self.engine.sim_config["earth_curvature"]) and self.attr.detected_method == "fixed":
                x0, y0, z0 = self.coords
                radius = self.attr.fixed_dis
                assert z0 >= 0
                _theta = np.arcsin(z0/radius)
                theta = np.linspace(-_theta, np.pi+_theta, 100)
                x = radius * np.cos(theta)
                z = radius * np.sin(theta)
                z += z0
                z = np.where(z < self.attr.max_height, z, self.attr.max_height)
                ax.plot(x+x0, z, "--", c=self.group, linewidth=1)
                ax.text(x[25]+x0, z[25], f"{self.name}探测远界", fontsize=6)
                ax.text(x[75]+x0, z[75], f"{self.name}探测远界", fontsize=6)
            elif self.engine.sim_config["earth_curvature"]:
                tag = ""
                _x1 = self._x1
                _x2 = self._x2
                _h = self._h
                if self.attr.detected_method in ["fixed", "prob"]:
                    foe_params = self.parent.engine.render_config["target"]
                    if self.attr.detected_method == "fixed":
                        dis = self._cal_dis_by_coef(foe_params=foe_params)
                        tag = f"[{foe_params['rcs']}m^2]"
                    else:
                        dis = self._cal_dis_by_formula(foe_params=foe_params)
                        tag = f"[{self.attr.prob}, {foe_params['rcs']}m^2]"
                    _h = np.where(_h < dis, _h, dis)
                    _x2_new = np.sqrt(dis**2-_h**2)
                    _x2 = np.where(_x2 <= _x2_new, _x2, _x2_new)
                    _x1 = np.where(_x1 <= _x2, _x1, _x2)
                x1 = np.r_[_x1, -1*_x1[::-1]]
                x2 = np.r_[_x2, -1*_x2[::-1]]
                h =  np.r_[_h, _h[::-1]]
                ax.plot(x1+x0, h, "--", c="black", linewidth=1)
                ax.plot(x2+x0, h, "--", c=self.group, linewidth=1)
                i = int(len(_h)/2)
                j = int(len(_h)/2) + len(_h)
                ax.text(x1[i]+x0, h[i], f"{self.name}探测近界", fontsize=6)
                ax.text(x1[j]+x0, h[j], f"{self.name}探测近界", fontsize=6)
                ax.text(x2[i]+x0, h[i], f"{self.name}探测远界"+tag, fontsize=6)
                ax.text(x2[j]+x0, h[j], f"{self.name}探测远界"+tag, fontsize=6)

            # 画探测到的目标
            found = set(self._found_target_tracks.keys())
            for t in found:
                x, y, z = t.coords
                ax.scatter(x, z, marker="*", c=t.group.lower(), s=20)

    cpdef draw3D(self, ax):
        if not self.engine.render_config["radar"]: return
        if self.is_on:
            self._update_interp()
            x, y, z = self.coords
            ax.plot_wireframe(self.attr.X1+x,self.attr.Y1+y,self.attr.Z1, color="black", linewidth=0.2)
            ax.plot_surface(self.attr.X1+x,self.attr.Y1+y,self.attr.Z1, color="black", alpha=0.2)
            ax.plot_wireframe(self.attr.X2+x,self.attr.Y2+y,self.attr.Z2, color=self.group, linewidth=0.2)
            ax.plot_surface(self.attr.X2+x,self.attr.Y2+y,self.attr.Z2, color=self.group, alpha=0.2)

    cpdef list drawSymbol(self):
        items = self._draw(mode="symbol")
        return items


cdef class GuiderBasedRadar(Radar):
    """
    """
    def __init__(self, unit, model):
        super().__init__(unit, model)
        self._guiding = {} #
        self._pre_guiding = defaultdict(lambda:0)
        self._commanders = set()

    cpdef turn_on(self):
        "开机"
        Radar.turn_on(self)
        self._send_guider_info()

    cpdef _render(self):
        """ 支持对web地图、庚图、白板的三种绘制模式 """
        if self.isactive and self.is_on:
            if self.engine.render_config["guider"]:
                self._render_range_update()
            else:
                special_effect.DynamicRangeEffect.kill(self.engine, self.ucname)
            self.engine.set_timer_triger(self._render, delay=self.engine.sim_interval()) # 每隔真实时间的1s更新一次
        else:
            special_effect.DynamicRangeEffect.kill(self.engine, self.ucname)

    cpdef turn_off(self):
        Radar.turn_off(self)
        self._send_guider_info()

    cpdef add_commander(self, commander):
        assert isinstance(commander, CLASS["AirCommander"])
        self._commanders.add(commander)
        commander.add_crossplatform_guider(self)
    
    property remain:
        def __get__(self):
            return self.attr["nwell"] - len(self._guiding.keys()) - len(self._pre_guiding)

    cpdef pre_load(self, foe):
        self.engine.log_command("%s %s预加载目标%s", LogCommandLabel.GUIDER_PRELOAD.value, self, foe)
        self._pre_guiding[foe] += 1
        self._send_guider_info()

    cpdef cancel_pre_load(self, foe):
        """ 撤销预加载目标 """
        assert self._pre_guiding[foe] > 0
        self._pre_guiding[foe] -= 1
        if self._pre_guiding[foe] == 0:
            del self._pre_guiding[foe]
        self.engine.log_command("%s %s撤销预加载目标%s", LogCommandLabel.GUIDER_PRELOAD_CANCEL.value, self, foe)
        self._send_guider_info()

    cpdef load(self, foe, int num):
        """ 
        """
        if foe in self._guiding:
            self._guiding[foe][0] += num
        else:
            self._guiding[foe] = [num]
        self.engine.log_command("%s %s加载目标%s", LogCommandLabel.GUIDER_LOAD.value, self, foe)
        self._send_guider_info()

    cpdef release(self, foe):
        """释放目标
        
        Args:
            foe: 目标对象
        """
        assert foe in self._guiding
        self._guiding[foe][0] -= 1
        if self._guiding[foe][0] == 0:
            self._guiding.pop(foe)
            self.engine.log_command("%s %s释放目标%s", LogCommandLabel.GUIDER_REALASE.value, self, foe)
            self._send_guider_info()

    cpdef load_ms(self, foe, ms):
        self._guiding[foe].append(ms)

    cpdef set _guide(self):
        self._update_jammers()
        cdef set seen = set()
        cdef list failure_mss = []
        cdef list foes = list(self._guiding.keys())
        for foe in foes:
            num, *mss = self._guiding[foe]
            assert num > 0
            if self.remain >= 0  and self.acquire(foe):
                content = message.event.EventIndicateInfo()
                for ms in mss:
                    self._send_event(ms.monitor, content)
                seen.add(foe)
        return seen

    cpdef _attack_handler(self, event):
        self.engine.log_info("%s Handle Attack Event", self)
        attacker = event.content.attacker
        target = event.content.target
        self.release(target)

    cpdef _send_guider_info(self):
        state_info = message.state_info.GuiderStateInfo(self.unit.name, self.name, self.model, self.remain, self._is_on)
        content = message.msg.MsgStateInfo(self.name, state_info)

    cpdef implement(self):
        Radar.implement(self)
        self._add_state("WORK", self._guide, self.attr.period) # 仅制导
        self._add_handler("EventMunitionAttackTarget", self._attack_handler)

    cpdef check(self):
        # super().check()
        assert self.attr.has_attr("nwell")
        assert self.attr.has_attr("class")
        assert self.attr.has_attr("period")
        assert self.attr.has_attr("up_angle")
        assert self.attr.has_attr("low_angle")
        assert self.attr.up_angle >= 0, "radar up_angle must be > 0"
        assert self.attr.low_angle <= 0, "radar low_angle must be < 0"
        assert self.attr.has_attr("antenna_height")
        assert self.attr.has_attr("max_height")
        assert self.attr.has_attr("max_distance")
        assert self.attr.has_attr("detected_method")
        assert self.attr.detected_method in ["formula", "prob", "fixed"]
        if self.attr.detected_method == "fixed":
            assert self.attr.has_attr("fixed_dis")
            assert isinstance(self.attr.fixed_dis, dict)
            if "normal" in self.attr.fixed_dis:
                self.engine.log_warning("%s中的参数fixed_dis中的normal关键字已不再使用，建议去掉；同时增加base_foe2参数", self)
            assert self.attr.has_attr("base_foe2")
            assert isinstance(self.attr.base_foe2, dict)
        elif self.attr.detected_method == "prob":
            assert self.attr.has_attr("prob")
            assert self.attr.has_attr("base_foe")
            assert isinstance(self.attr.base_foe, dict)
            assert 0.0 < self.attr.prob < 1.0
        else:
            assert self.attr.has_attr("base_foe")
            assert isinstance(self.attr.base_foe, dict)

    cpdef draw(self, ax):
        Radar.draw(self, ax)
        if self.engine.render_config["guide_line"]:
            foes = list(self._guiding.keys())
            x0, y0, _ = self.coords
            for foe in foes:
                x1, y1, _ = foe.coords
                ax.plot([x0, x1], [y0, y1], "--", c=self.group, linewidth=1)


cdef class RadarWithGuider(GuiderBasedRadar):
    """
    """

    def __init__(self, unit, model):
        super().__init__(unit, model)
        self.plat_at_home = False

    cpdef bint acquire(self, foe):
        return GuiderBasedRadar.acquire(self, foe)

    cpdef set _search(self):
        cdef set foes = set([e for e in self.engine.actives() if e.isdetectable and e.group != self.group 
                        and isinstance(e, (platform.Ship, platform.Plane, platform.Submarine))])
        cdef set guide_foes = set(self._guiding.keys())
        cdef set guide_seen = self._guide()
        cdef set seen = set(filter(self.acquire, foes-guide_foes))
        seen = seen.union(guide_seen)
        return seen

    cpdef _detect(self):
        if self.plat_at_home and self.is_on:
            self.turn_off()
        elif (self.plat_at_home == True) and (self.is_on == False):
            return
        elif (self.plat_at_home == False) and (self.is_on == True):
            GuiderBasedRadar._detect(self)

    cpdef _attack_handler(self, event):
        GuiderBasedRadar._attack_handler(self, event)

    cpdef implement(self):
        GuiderBasedRadar.implement(self)
        self._add_state("WORK", self._detect, self.attr.period)
        self._add_handler("EventMunitionAttackTarget", self._attack_handler)

    cpdef check(self):
        GuiderBasedRadar.check(self)
        assert self.attr.has_attr("yield_time")
        assert self.attr.has_attr("update_time")
        assert self.attr.update_time >= self.attr.period
        assert self.attr.yield_time >= self.attr.update_time

    cpdef _render(self): 
        """ 支持对web地图、庚图、白板的三种绘制模式 """
        if self.isactive and self.is_on:
            if self.engine.render_config["radar"] or self.engine.render_config["guider"]:
                self._render_range_update()
            else:
                special_effect.DynamicRangeEffect.kill(self.engine, self.ucname)
            self.engine.set_timer_triger(self._render, delay=self.engine.sim_interval()) # 每隔真实时间的1s更新一次
        else:
            special_effect.DynamicRangeEffect.kill(self.engine, self.ucname)