import os
import sys
import time
import json
import socket
import threading
import argparse
import requests

import numpy as np
import pandas as pd
import collections
import matplotlib as mpl


mpl.use("Agg")
mpl.rcParams["font.sans-serif"] = ["SimHei"]
mpl.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt

import simulation.algorithm as alg
import simulation.database as database
import simulation.core as core
import simulation.arsenal as asn
import simulation.utilities as utl

from simulation.core import CLASS, special_effect

# 双方兵力配置: 15 USV + 15 UAV
NUM_UNITS = 15  # 每方USV和UAV数量
MY_Y_BASE = 300000   # 我方USV起始y
MY_Y_STEP = 15000    # 我方USV y间隔
ENEMY_X = 260000     # 敌方起始x

@utl.check.check_sim
def sim(simserver=None, engine_name='20250803水面所仿真2', web_ip=None, gengtu_ip=None, user_name='admin',
        render_config=None, checkbox_dict=None, logtag=None, uav_speed=150):
    flag = core.log.DECISION
    engine = core.tzb_engine.TzbEngine(engine_name, epoch=None, flag=flag, logpath=None, terminal=False, logtag=logtag,
                                cache=True, render_config=render_config, checkbox_dict=checkbox_dict,
                                web_ip=web_ip, user_name=user_name, simserver=simserver)

    # ========== 渲染配置 ==========
    engine.render_config.update({"name": True})
    engine.render_config.update({"lethality": False})
    engine.render_config.update({"radar": True})
    engine.render_config.update({"crosspoint": False})
    engine.render_config.update({"network_link": False})
    engine.render_config.update({"waypoints_units": "all"})

    engine.render_config.update({"target": {"rcs": 0.1, "speed": 255, "height": 20, "type_": "B-1B"}})
    engine.sim_config.update({"ignore_com": False})
    engine.sim_config.update({"earth_curvature": False})

    engine.set_end_time(600000)
    engine.set_ratio(50)  # 50x仿真(15+15单位多, 降低倍速保稳定性)

    # 加载作战区域
    with open("/root/autodl-tmp/hsystem/hsystem/sim_script/20250819TZB/Demo/任务区域.json", 'r', encoding='utf-8') as f1:
        area = json.load(f1)

    points_area = [item for i, item in area.items()]
    special_effect.StaticPolygonEffect.gen(engine, "Area", points=points_area, color='green', alpha=0, fill_alpha=0, coordinate_system="Cartesian")

    # ═══════ 我方兵力: 15 USV + 15 UAV ═══════
    # 我方USV/UAV初始位置: x=0, y从300k起间隔15k
    ships_xy = {f'white_usv{i}': [0, MY_Y_BASE + (i-1)*MY_Y_STEP] for i in range(1, NUM_UNITS+1)}
    uav_swarm_xy = {f'white_uav{i}': [0, MY_Y_BASE + (i-1)*MY_Y_STEP] for i in range(1, NUM_UNITS+1)}

    """配置白方USV参数"""
    engine.db["RadarWithGuider"]["distance"] = 35_000
    engine.db["RadarWithGuider"]["sector"] = [0, 360]
    engine.db["RadarWithGuider"]["detected_method"] = "fixed"
    engine.db["Ship"]["comdev"] = "Comdev"
    engine.db["Ship"]["emitters"] = []
    engine.db["Ship"]["guiders"] = []
    engine.db["Ship"]["motor"] = "ShipMotorTZB"
    engine.db["Ship"]["radars"] = ["RadarWithGuider"]

    # 生成我方USV
    white_usvs = []
    for _i in range(1, NUM_UNITS+1):
        _usv = engine.gen_platform(f'white_usv{_i}', 'Ship', 'RED', ships_xy[f'white_usv{_i}'], 10, 90, coordinate_system="Cartesian")
        white_usvs.append(_usv)

    """配置白方UAV参数"""
    engine.db["RadarWithGuider"]["distance"] = 60_000
    engine.db["RadarWithGuider"]["sector"] = [-30, 30]
    engine.db["RadarWithGuider"]["detected_method"] = "fixed"
    engine.db["PlaneMotorTZB"]["max_speed"] = 150
    engine.db["AEW"]["motor"] = "PlaneMotorTZB"
    engine.db["AEW"]["radars"] = ["RadarWithGuider"]
    engine.db["AEW"]["comdev"] = "Comdev"

    # 生成我方UAV(每艘USV配1架)
    white_uavs = []
    for _i in range(1, NUM_UNITS+1):
        _uav = engine.gen_platform(f'white_uav{_i}', 'AEW', 'RED', uav_swarm_xy[f'white_uav{_i}'], uav_speed, 90, 100, coordinate_system="Cartesian")
        white_uavs.append(_uav)

    reds = white_usvs + white_uavs  # 所有红方单位

    # 星型网络(以white_usv1为中心)
    all_white_names = [f'white_usv{i}' for i in range(1, NUM_UNITS+1)] + [f'white_uav{i}' for i in range(1, NUM_UNITS+1)]
    engine.gen_star_network("StarNetwork4", 'white_usv1', all_white_names)

    # ═══════ 敌方兵力: 15 USV + 15 UAV ═══════
    """配置黑方USV参数"""
    engine.db["RadarWithGuider"]["distance"] = 30_000
    engine.db["RadarWithGuider"]["sector"] = [0, 360]
    engine.db["Ship"]["comdev"] = "Comdev"
    engine.db["Ship"]["emitters"] = []
    engine.db["Ship"]["guiders"] = []
    engine.db["Ship"]["motor"] = "ShipMotorTZB"
    engine.db["Ship"]["radars"] = ["RadarWithGuider"]

    engine.cache["num_black_usv"] = NUM_UNITS

    blues = []  # 所有蓝方单位
    black_usvs = []
    for _i in range(1, NUM_UNITS+1):
        _y = MY_Y_BASE + (_i-1)*MY_Y_STEP
        # 敌方USV: 在x=260k, 向西巡逻
        _b = engine.gen_platform(f'black_usv{_i}', 'Ship', 'BLUE',
                                 [ENEMY_X, _y], 10, 0, coordinate_system="Cartesian")
        black_usvs.append(_b)
        blues.append(_b)
        # 向西巡逻航路点
        engine.cmd_sail_area(_b, speed=10, xy_points=[[ENEMY_X, _y], [ENEMY_X//2, _y], [0, _y]])

    """配置黑方UAV参数(侦察)"""
    engine.db["RadarWithGuider"]["distance"] = 60_000
    engine.db["RadarWithGuider"]["sector"] = [-30, 30]
    engine.db["AEW"]["motor"] = "PlaneMotorTZB"
    engine.db["AEW"]["radars"] = ["RadarWithGuider"]
    engine.db["AEW"]["comdev"] = "Comdev"

    # 生成敌方UAV(每艘USV配1架), 向西巡逻
    black_uavs = []
    for _i in range(1, NUM_UNITS+1):
        _y = MY_Y_BASE + (_i-1)*MY_Y_STEP
        _bu = engine.gen_platform(f'black_uav{_i}', 'AEW', 'BLUE',
                                  [ENEMY_X, _y], uav_speed, 0, 100, coordinate_system="Cartesian")
        black_uavs.append(_bu)
        blues.append(_bu)
        engine.cmd_sail_area(_bu, speed=30, xy_points=[[ENEMY_X, _y], [ENEMY_X//2, _y], [0, _y]])

    """设置裁判系统"""
    all_units = reds + blues
    judge = engine.gen_judge_system("JudgeSystemTZB", all_units)
    judge_area = points_area + [points_area[0]]
    judge.set_area(judge_area)

    def start(engine):
        """仿真启动时的初始化操作"""
        engine.turn_on_radars()
        engine.turn_on_lockers()
        for _uav in white_uavs:
            _uav.uavbattery.turn_on()
        for _bu in black_uavs:
            _bu.uavbattery.turn_on()
        judge.activate()
        for _i in range(1, NUM_UNITS+1):
            engine.put_uav_in_ship(f'white_uav{_i}', f'white_usv{_i}')
    engine.set_starter(start)

    def black_strategy(engine):
        """黑方AI: USV锁定我方USV, UAV提供侦察"""
        detected = engine.get_black_targets()
        for _b_unit in black_usvs:
            for _w_unit_name in detected:
                if "usv" in _w_unit_name:
                    engine.black_cmd_lock(_b_unit.name, _w_unit_name)

    # 黑方AI每秒执行一次
    engine.add_manipulator(black_strategy, 1)

    return engine


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='M simulation')
    parser.add_argument("--para", type=str, help="simulation params")
    parser.add_argument("--iter", type=str, help="simulation iter")
    args = parser.parse_args()

    if args.para:
        para = eval(args.para)
        [uav_speed] = para
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        logtag =  f'{hostname}'
        engine = sim(logtag=logtag, uav_speed=uav_speed)
    else:
        uav_speed = 150
        engine = sim(web_ip='127.0.0.1', user_name="admin", logtag="test", uav_speed=uav_speed)
    engine.activate()
    engine.update()
