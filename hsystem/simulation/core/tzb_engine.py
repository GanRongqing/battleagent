from simulation import core
from .base_engine import CmdData
from . import log, enums, base_engine
import simulation.arsenal as asn
import simulation.algorithm as alg
import json
import asyncio

class TzbEngine(core.engine.Engine):
    """ 仿真调度引擎
    """

    def __init__(self, name="engine", epoch=None, flag=log.INFO, terminal=True, logtag=None, logpath=None,
                 db=None, cache=True, raise_error=enums.RaiseErrorFlag.DEBUG, redis_ip=None, redis_log=False, render_config=None,
                 checkbox_dict=None, web_ip=None, user_name='test', new_thread=True, simserver=None, udp_ip=None,
                 nats_ip=None):
        super().__init__(name, epoch, flag, terminal, logtag, logpath, db, cache, raise_error, redis_ip, redis_log, render_config,
                         checkbox_dict, web_ip, user_name, new_thread, simserver, udp_ip, nats_ip)

    def get_state(self):
        # 动态统计双方兵力数量(支持任意兵力规模)
        _nw = _nb = _wu = _bu = 0
        for _u in self.judge.units_all:
            if _u.group == "RED" and isinstance(_u, asn.platform.Ship):
                _nw += 1
            elif _u.group == "BLUE" and isinstance(_u, asn.platform.Ship):
                _nb += 1
            elif _u.group == "RED" and isinstance(_u, asn.platform.Plane):
                _wu += 1
            elif _u.group == "BLUE" and isinstance(_u, asn.platform.Plane):
                _bu += 1

        states = {
            "time": self.engine.time,
            "ratio": self.engine.ratio,
            "num_white_usv": _nw,
            "num_black_usv": _nb,
            "num_white_uav": _wu,
            "num_black_uav": _bu,
            "white_usv_states": [],
            "white_uav_states": [],
            "black_usv_states": [],
            "black_uav_states": [],
            "white_observation": [],
            "ended": False,
            "ended_reason": "",
            "env_score_flat": {},
        }

        # 统计存活数量
        white_ship_alive = 0
        white_uav_alive = 0
        black_ship_alive = 0

        for unit in self.judge.units_all:
            if unit.group == "RED" and isinstance(unit, asn.platform.Ship):
                state = {}
                state['name'] = unit.name
                state["is_alive"] = unit.isactive
                if unit.isactive:
                    white_ship_alive += 1
                    # 动力学状态，包括position，velocity， course， speed
                    dynamic_state = unit.motor.get_ship_state()
                    for key, value in dynamic_state.items():
                        state[key] = value
                    state['is_locked'] = unit.locker.locked
                    state['is_locking'] = unit.locker.locking
                    state['is_frozen'] = unit.locker.frozen
                    state['locked_attacker'] = unit.locker.emy_name
                    state['relative_orientation'] = []
                    if state['locked_attacker']:
                        for _ele in state['locked_attacker']:
                            _attacker = self.unit_by_name(_ele)
                            state['relative_orientation'].append(alg.geo.azimuth(unit.coords, _attacker.coords))
                    state['locking_unit'] = unit.locker.locking_name
                    state['uav'] = unit.planes
                state["locked_times"] = unit.locker.locked_times
                states['white_usv_states'].append(state)
            elif unit.group == "RED" and isinstance(unit, asn.platform.Plane):
                state = {}
                state['name'] = unit.name
                state["is_alive"] = unit.isactive
                if unit.isactive:
                    white_uav_alive += 1
                    # 动力学状态，包括position，velocity， course， speed
                    dynamic_state = unit.motor.get_ship_state()
                    for key, value in dynamic_state.items():
                        state[key] = value
                    state['battery'] = unit.uavbattery.fly_time_remain
                    state['battery_format'] = max(unit.uavbattery.fly_time_remain,
                                                  0) / unit.uavbattery.total_fly_time * 100
                    state['is_charging'] = unit.uavbattery.charging
                    state['is_at_usv'] = unit.is_at_home
                    state['home_name'] = unit.ship_home
                states['white_uav_states'].append(state)
            elif unit.group == "BLUE" and isinstance(unit, asn.platform.Ship):
                state = {}
                state['name'] = unit.name
                state["is_alive"] = unit.isactive
                if unit.isactive:
                    black_ship_alive += 1
                    state['is_frozen'] = unit.locker.frozen
                state["locked_times"] = unit.locker.locked_times
                states['black_usv_states'].append(state)
            elif unit.group == "BLUE" and isinstance(unit, asn.platform.Plane):
                # 敌方UAV状态
                state = {}
                state['name'] = unit.name
                state["is_alive"] = unit.isactive
                if unit.isactive:
                    dynamic_state = unit.motor.get_ship_state()
                    for key, value in dynamic_state.items():
                        state[key] = value
                    state['battery_format'] = max(unit.uavbattery.fly_time_remain,
                                                  0) / unit.uavbattery.total_fly_time * 100
                    state['is_at_usv'] = unit.is_at_home
                states['black_uav_states'].append(state)
        states['white_observation'], _ = self.get_white_targets()

        # ── P0-1: 对局结束条件判断 ──
        black_breakthrough = len(self.judge.black_success)
        total_white_alive = white_ship_alive + white_uav_alive

        if total_white_alive == 0:
            states["ended"] = True
            states["ended_reason"] = "我方所有单位被击毁"
        elif black_ship_alive == 0:
            states["ended"] = True
            states["ended_reason"] = "敌方所有单位被击毁"
        elif black_breakthrough > 0:
            states["ended"] = True
            states["ended_reason"] = f"敌方{black_breakthrough}艘艇突破防线"
        elif not self.isactive:
            states["ended"] = True
            states["ended_reason"] = "仿真引擎已停止"

        # ── P0-2: 奖励信号 ──
        cs = self.judge.cumulative_score
        states["env_score_flat"] = {
            "black_killed": cs["black_killed"],
            "black_hit": cs["black_hit"],
            "white_ship_killed": cs["white_ship_killed"],
            "white_uav_killed": cs["white_uav_killed"],
            "black_breakthrough": cs["black_breakthrough"],
            "white_hit": cs["white_hit"],
            "collision": cs["collision"],
        }

        return states

    def send_command(self, cmd):
        unit = self.get_unit(cmd["unit_name"])
        if unit.group != "RED":
            print(f"{unit}并非白方平台，不能外部控制！")
            return
        if not isinstance(unit.motor, asn.tzb_motor.MotorTZB):
            print(f"受控对象{unit}Motor类型不匹配！")
            return
        target_speed = cmd["target_speed"]
        target_course = cmd["target_course"]
        if target_speed < 0:
            print(f"{unit}设置的目标速度{target_speed}不在允许范围内！")
            return
        if target_course < 0 or target_course > 360:
            print(f"{unit}设置的目标方向{target_course}不在允许范围内（0-360）")
            return
        unit.motor.set_target_speed(target_speed)
        unit.motor.set_target_angle(target_course)
        print(f"{unit}收到控制指令，目标速度{target_speed}，目标方向{target_course}")