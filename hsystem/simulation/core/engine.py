from audioop import error

from .base_engine import CmdData
from . import log, enums, base_engine
from simulation.core import log, enums, special_effect, CLASS
import simulation.algorithm as alg
import simulation.arsenal as asn
import json
import asyncio

class Engine(base_engine.BaseEngine):
    """ 仿真调度引擎
    """

    def __init__(self, name="engine", epoch=None, flag=log.INFO, terminal=True, logtag=None, logpath=None,
                 db=None, cache=True, raise_error=enums.RaiseErrorFlag.DEBUG, redis_ip=None, redis_log=False, render_config=None,
                 checkbox_dict=None, web_ip=None, user_name='test', new_thread=True, simserver=None, udp_ip=None,
                 nats_ip=None):
        super().__init__(name, epoch, flag, terminal, logtag, logpath, db, cache, raise_error, redis_ip, redis_log, render_config,
                         checkbox_dict, web_ip, user_name, new_thread, simserver, udp_ip, nats_ip)

    def turn_on_sensor(self, sensor):
        """
        Args:
        Returns:

        """
        sensor = self.get_comp(sensor)
        sensor.turn_on()

    def turn_on_sensors(self, sensors):
        """
        Args:
        Returns:

        """
        for sensor in sensors:
            self.turn_on_sensor(sensor)

    def turn_on_radars(self, unames=None):
        """
        Args:
        Returns:

        """
        if unames is None:
            for unit in self.units():
                if hasattr(unit, "radars"):
                    for radar in unit.radars:
                        if radar.isactive and (not radar.is_on):
                            radar.turn_on()
        else:
            for name in unames:
                unit = self.unit_by_name(name)
                if hasattr(unit, "radars"):
                    for radar in unit.radars:
                        if radar.isactive and (not radar.is_on):
                            radar.turn_on()

    def turn_off_sensor(self, sensor):
        """
        Args:
        Returns:

        """
        sensor = self.get_comp(sensor)
        if sensor.isactive:
            sensor.turn_off()

    def turn_off_sensors(self, sensors):
        """
        Args:
        Returns:

        """
        for sensor in sensors:
            self.turn_off_sensor(sensor)

    def turn_off_radars(self, unames=None):
        """
        Args:
            unames:平台名称(List<str>) Defaults to None
        Returns:

        """
        if unames is None:
            for unit in self.units():
                if hasattr(unit, "radars"):
                    for radar in unit.radars:
                        if radar.isactive and radar.is_on:
                            radar.turn_off()
        else:
            for name in unames:
                unit = self.unit_by_name(name)
                if hasattr(unit, "radars"):
                    for radar in unit.radars:
                        if radar.isactive and radar.is_on:
                            radar.turn_off()

    def turn_on_lockers(self, unames=None):
        """
        锁定功能开机
        Args:
            unames:平台名称(List<str>) Defaults to None

        Returns:

        """
        if unames is None:
            for unit in self.units():
                if hasattr(unit, "locker"):
                    if unit.locker.isactive and (not unit.locker.is_on):
                        unit.locker.turn_on()
        else:
            for name in unames:
                unit = self.unit_by_name(name)
                if hasattr(unit, "locker"):
                    if unit.locker.isactive and (not unit.locker.is_on):
                        unit.locker.turn_on()

    def turn_off_lockers(self, unames=None):
        """
        锁定功能关机
        Args:
            unames:平台名称(List<str>) Defaults to None

        Returns:

        """
        if unames is None:
            for unit in self.units():
                if hasattr(unit, "locker"):
                    if unit.locker.isactive and unit.locker.is_on:
                        unit.locker.turn_off()
        else:
            for name in unames:
                unit = self.unit_by_name(name)
                if hasattr(unit, "locker"):
                    if unit.locker.isactive and unit.locker.is_on:
                        unit.locker.turn_off()

    def set_relation_intels(self, superior, juniors):
        """
        Args:
        Returns:

        """
        superior_intel = self.get_intel(superior)
        assert superior_intel is not None
        for junior in juniors:
            junior_intel = self.get_intel(junior)
            assert junior_intel is not None
            assert self.check_isin_network(superior_intel.unit, junior_intel.unit)
            junior_intel.add_superior_intel(superior_intel)

    def set_relation_intel_comps(self, intel, comps):
        """
        Args:
        Returns:

        """
        intel = self.get_intel(intel)
        assert intel is not None
        for c in comps:
            comp = self.get_comp(c)
            assert self.check_isin_network(intel.unit, comp.unit)
            intel.add_consumer(comp)

    def cmd_plane_patrol(self, plane, speed=None, xy_points=None, lnglat_points=None,
                         cmd_res_name: str = None):
        """
        Args:
            plane: 接收指令的飞机(str)
            speed:飞行速度 m/s Defaults to None(int)
            waypoints:路径点列表 Defaults to None(list)
            cmd_track:是否追踪指令执行状态 Defaults to False(Bool)

        Returns:
        """
        cmd = CmdData(self, "cmd_plane_patrol", "在指定空域巡逻", self.time, cmd_res_name=cmd_res_name)
        plane = self.get_unit(plane)

        if speed is None:
            speed = plane.speed
        for radar in plane.radars:
            if not radar.is_on:
                radar.turn_on()
        height = plane.coords[2]
        waypoints = self.get_waypoints(None, xy_points, lnglat_points, height)
        if waypoints is not None:
            self.insert_maneuver_cmd(plane,
                                     {"mode": "waypoints", "waypoints": waypoints, "speed": speed, "repeat": True,
                                      "cmd_name": cmd.cmd_name}, rightnow=True)
        else:
            self._execute_maneuver_cmd(plane, {"mode": "Hover", "repeat": True, "cmd_name": cmd.cmd_name},
                                       rightnow=True)

        return -1, cmd.cmd_name  # -1表示执行时长不确定

    def gen_judge_system(self, model, units):
        model_dct = self.db[model]
        cls_ = CLASS[model_dct["class"]]
        judge = cls_(self, model)
        judge.set_units(units)
        self.judge = judge
        return judge

    def gen_star_network(self, model, center_uname, unames):
        """
        Args:
        """
        # assert not self.sim_config['ignore_com'], "仅在不忽略通信限制模式下允许建立通信网络"
        model_dct = self.db[model]
        cls_ = CLASS[model_dct["class"]]
        network = cls_(self, model)
        if self._is_started:  # 如果引擎已启动start，则手动激活
            network.activate()
        c = self.unit_by_name(center_uname)
        assert c.comdev is not None
        network.add_center_comdev(c.comdev)
        for name in unames:
            p = self.unit_by_name(name)
            assert p.comdev is not None
            network.add_comdev(p.comdev)
        # 在 network 初始化时, 已经将 network 添加至 engine 中, 此处注释
        # self._networks.append(network)
        return network

    def get_intel_targets(self, unit_name):
        """
        返回unit_name情报系统中的targets
        Args:
            unit_name: 平台的名字(str)

        Returns:情报系统中探测到的目标实例targets(list)

        """
        if isinstance(unit_name, str):
            p1 = self.unit_by_name(unit_name)
            targets = p1.intelligence.targets
            name_list = [_target.name for _target in targets]
            return name_list
        else:
            raise RuntimeError(str(unit_name) + " is not str!")

    def get_white_targets(self):
        """
        Args:
        """
        white_targets = set()
        white_target_info = []
        for unit in self.units():
            if unit.group == "RED":
                name_list = self.get_intel_targets(unit.name)
                white_targets = white_targets.union(set(name_list))
        _other_blues = []
        for unit in self.units():
            # 只有BLUE的Ship才有locker, UAV没有
            if unit.group == "BLUE" and isinstance(unit, asn.platform.Ship):
                if unit.locker.locked:
                    _other_blues.append(unit.name)
                if unit.locker.frozen:
                    _other_blues.append(unit.name)
                white_targets = white_targets.union(set(_other_blues))
        for unit_name in white_targets:
            _target_info = {}
            _unit = self.unit_by_name(unit_name)
            _target_info['name'] = unit_name
            _target_info['position'] = list(_unit.coords)
            _target_info['velocity'] = list(_unit.velocity)
            white_target_info.append(_target_info)
        return white_target_info, list(white_targets)

    def get_black_targets(self):
        """
        Args:
        """
        black_targets = set()
        for unit in self.units():
            if unit.group == "BLUE":
                name_list = self.get_intel_targets(unit.name)
                black_targets = black_targets.union(set(name_list))
        return list(black_targets)

    def cmd_lock(self, unit1_name, unit2_name):
        if isinstance(unit1_name, str) and isinstance(unit2_name, str):
            attacker = self.unit_by_name(unit1_name)
            target = self.unit_by_name(unit2_name)
            if not isinstance(attacker, asn.platform.Ship):
                print("只有无人船才具有锁定功能！！！")
                return False
            if not isinstance(target, asn.platform.Ship):
                print("只有无人船才能被锁定！！！")
                return False
            if attacker.group == target.group:
                print("同阵营的智能体无法相互锁定！！！")
                return False
            if attacker.group != "RED":
                print(f"{unit1_name}不是白方阵营！！！")
                return False
            _, white_targets = self.get_white_targets() # 收集所有可用目标
            if unit2_name in white_targets:
                if alg.geo.distance(attacker.coords, target.coords) < 40_000:
                    _res1 = target.locker.is_locked(unit1_name)
                    if _res1:
                        _res2 = attacker.locker.is_locking(unit2_name)
                        if _res2:
                            return True
                        else:
                            print(f"{unit1_name}正在锁定其它目标(一个无人船只能同时锁定一个目标，不可切换)")
                            return False
                else:
                    print(f"{unit2_name}不在{unit1_name}的锁定范围内！")
                    return False
            else:
                print(f"{unit2_name}不在白方的视野范围内！")
                return False
        else:
            raise RuntimeError(str(unit1_name) + "or" + str(unit2_name)+ " is not str!")
        
    def black_cmd_lock(self, unit1_name, unit2_name):
        if isinstance(unit1_name, str) and isinstance(unit2_name, str):
            unit1 = self.unit_by_name(unit1_name)
            unit2 = self.unit_by_name(unit2_name)
            if not isinstance(unit1, asn.platform.Ship):
                print("只有无人船才具有锁定功能！！！")
                return False
            if not isinstance(unit2, asn.platform.Ship):
                print("只有无人船才具有锁定功能！！！")
                return False
            assert unit1.group != unit2.group
            assert unit1.group == "BLUE"
            if unit2_name in self.get_black_targets():
                if alg.geo.distance(unit1.coords, unit2.coords) < 40_000:
                    _res1 = unit2.locker.is_locked(unit1_name)
                    if _res1:
                        _res2 = unit1.locker.is_locking(unit2_name)
                        if _res2:
                            return True
                        else:
                            return False
                    else:
                        return False
                else:
                    return False
            else:
                # print(f"{unit2_name}不在黑方的视野范围内！")
                return False
        else:
            raise RuntimeError(str(unit1_name) + "or" + str(unit2_name)+ " is not str!")

    def cmd_uav_takeoff(self, unit_name, home_name, target_speed=150, target_course=0):
        if isinstance(unit_name, str) and isinstance(home_name, str):
            unit1 = self.unit_by_name(unit_name)
            unit2 = self.unit_by_name(home_name)
            if isinstance(unit1, asn.platform.Plane) and isinstance(unit2, asn.platform.Ship):
                return unit1.take_off(unit_name, home_name, target_speed, target_course)
            else:
                return False
        else:
            raise RuntimeError(str(unit_name) + "or" + str(home_name) + " is not str!")

    def cmd_uav_land(self, uav_name, usv_name):
        if isinstance(uav_name, str) and isinstance(usv_name, str):
            unit1 = self.unit_by_name(uav_name)
            unit2 = self.unit_by_name(usv_name)
            assert unit1.group == unit2.group
            if alg.geo.distance(unit1.coords[:2], unit2.coords[:2]) < 10000 and unit1.speed < 100:
                if isinstance(unit1, asn.platform.Plane) and isinstance(unit2, asn.platform.Ship):
                    return unit1.land(usv_name)
            else:
                return False
        else:
            raise RuntimeError(str(uav_name) + "or" + str(usv_name) + " is not str!")

    def put_uav_in_ship(self, uav_name, ship_name):
        if isinstance(uav_name, str) and isinstance(ship_name, str):
            unit1 = self.unit_by_name(uav_name)
            unit2 = self.unit_by_name(ship_name)
            assert isinstance(unit1, asn.platform.Plane)
            assert isinstance(unit2, asn.platform.Ship)
            result = unit2.load_uav(uav_name)
            if result:
                unit1.is_at_home = True
                # unit2.add_child(unit1)
                unit1.home_unit = unit2
                unit1.ship_home = ship_name
                unit1.motor.set_at_home(ship_name)
                unit1.radars[0].plat_at_home = True
            return result
        else:
            raise RuntimeError(str(uav_name) + "or" + str(ship_name) + " is not str!")

    def get_all_state(self):
        if not hasattr(self, "judge"):
            print("未设置才裁判系统！！！！！！！！")
            return {}

        states = {
            "time": self.engine.time,
            "white_usv_states": [],
            "white_uav_states": [],
            "white_observation": [],
            "judge_system_info":{}
        }
        for unit in self.judge.units_all:
            if unit.group=="RED" and isinstance(unit, asn.platform.Ship):
                state = {}
                state['name'] = unit.name
                state["is_alive"] = unit.isactive
                if unit.isactive:
                    # 动力学状态，包括position，velocity， course， speed
                    dynamic_state = unit.motor.get_ship_state()
                    for key, value in dynamic_state.items():
                        state[key] = value
                    state['is_locked'] = unit.locker.locked
                    state['is_locking'] = unit.locker.locking
                    state['is_frozen'] = unit.locker.frozen
                    state['locked_attacker'] = unit.locker.emy_name
                    state['locking_unit'] = unit.locker.locking_name
                    state['uav'] = unit.planes
                states['white_usv_states'].append(state)
            elif unit.group=="RED" and isinstance(unit, asn.platform.Plane):
                state = {}
                state['name'] = unit.name
                state["is_alive"] = unit.isactive
                if unit.isactive:
                    # 动力学状态，包括position，velocity， course， speed
                    dynamic_state = unit.motor.get_ship_state()
                    for key, value in dynamic_state.items():
                        state[key] = value
                    state['battery'] = unit.uavbattery.fly_time_remain
                    state['battery_format'] = max(unit.uavbattery.fly_time_remain, 0)/unit.uavbattery.total_fly_time*100
                    state['is_charging'] = unit.uavbattery.charging
                    state['is_at_usv'] = unit.is_at_home
                    state['home_name'] = unit.ship_home
                states['white_uav_states'].append(state)
        states['white_observation'], _ = self.get_white_targets()
        states['judge_system_info']['black_success_num'] = len(self.judge.black_success)
        states['judge_system_info']['black_locked_num'] = self.judge.black_locked_num
        states['judge_system_info']['white_locked_num'] = self.judge.white_locked_num
        states['judge_system_info']['collide_num'] = self.judge.collide_num

        return states
