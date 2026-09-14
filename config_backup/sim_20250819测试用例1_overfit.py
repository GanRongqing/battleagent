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

# 配置参数
@utl.check.check_sim # 装饰器：检查仿真参数合法性
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
    engine.set_ratio(100)  # 100x仿真: 锁定300s=3s真实时间

    # with open("Demo/任务区域.json", 'r', encoding='utf-8') as f1:
    #     area = json.load(f1)
    # with open("Demo/方案3-黑方艇数量_5.json", 'r', encoding='utf-8') as f2:
    #     black_waypoints = json.load(f2)

    with open("/root/autodl-tmp/hsystem/hsystem/sim_script/20250819TZB/Demo/任务区域.json", 'r', encoding='utf-8') as f1:
        area = json.load(f1)
    with open("/root/autodl-tmp/hsystem/hsystem/sim_script/20250819TZB/Demo/方案3-黑方艇数量_5.json", 'r', encoding='utf-8') as f2:
       black_waypoints = json.load(f2)

    engine.cache["num_black_usv"] = 5

    points_area = [item for i, item in area.items()]
    special_effect.StaticPolygonEffect.gen(engine, "Area", points=points_area, color='green', alpha=0, fill_alpha=0, coordinate_system="Cartesian")
    ships_xy = {"white_usv1":[0, 537000], "white_usv2":[0, 487000], "white_usv3":[0, 337000], "white_usv4":[0, 187000], "white_usv5":[0, 137000]}
    uav_swarm_xy = {"white_uav1":[0, 537000], "white_uav2":[0, 487000], "white_uav3":[0, 337000], "white_uav4":[0, 187000], "white_uav5":[0, 137000]}

    """"配置白方USV参数"""
    engine.db["RadarWithGuider"]["distance"] = 35_000  # 超过黑方30km, 先敌发现
    engine.db["RadarWithGuider"]["sector"] = [0, 360]
    engine.db["RadarWithGuider"]["detected_method"] = "fixed"
    engine.db["Ship"]["comdev"] = "Comdev"
    engine.db["Ship"]["emitters"] = []
    engine.db["Ship"]["guiders"] = []
    engine.db["Ship"]["motor"] = "ShipMotorTZB"
    engine.db["Ship"]["radars"] = ["RadarWithGuider"]

    r1 = engine.gen_platform('white_usv1', 'Ship', 'RED', ships_xy["white_usv1"], 10, 90, coordinate_system="Cartesian")
    r2 = engine.gen_platform('white_usv2', 'Ship', 'RED', ships_xy["white_usv2"], 10, 90, coordinate_system="Cartesian")
    r3 = engine.gen_platform('white_usv3', 'Ship', 'RED', ships_xy["white_usv3"], 10, 90, coordinate_system="Cartesian")
    r4 = engine.gen_platform('white_usv4', 'Ship', 'RED', ships_xy["white_usv4"], 10, 90, coordinate_system="Cartesian")
    r5 = engine.gen_platform('white_usv5', 'Ship', 'RED', ships_xy["white_usv5"], 10, 90, coordinate_system="Cartesian")

    """"配置白方UAV参数"""
    engine.db["RadarWithGuider"]["distance"] = 60_000
    engine.db["RadarWithGuider"]["sector"] = [-30, 30]
    engine.db["RadarWithGuider"]["detected_method"] = "fixed"

    # 修改无人机最大速度
    engine.db["PlaneMotorTZB"]["max_speed"] = 150

    engine.db["AEW"]["motor"] = "PlaneMotorTZB"
    engine.db["AEW"]["radars"] = ["RadarWithGuider"]
    engine.db["AEW"]["comdev"] = "Comdev"

    uav1 = engine.gen_platform(f'white_uav1', 'AEW', 'RED',uav_swarm_xy["white_uav1"], uav_speed,90, 100, coordinate_system="Cartesian")
    uav2 = engine.gen_platform(f'white_uav2', 'AEW', 'RED',uav_swarm_xy["white_uav2"], uav_speed,90, 100, coordinate_system="Cartesian")
    uav3 = engine.gen_platform(f'white_uav3', 'AEW', 'RED',uav_swarm_xy["white_uav3"], uav_speed,90, 100, coordinate_system="Cartesian")
    uav4 = engine.gen_platform(f'white_uav4', 'AEW', 'RED',uav_swarm_xy["white_uav4"], uav_speed,90, 100, coordinate_system="Cartesian")
    uav5 = engine.gen_platform(f'white_uav5', 'AEW', 'RED',uav_swarm_xy["white_uav5"], uav_speed,90, 100, coordinate_system="Cartesian")

    reds = [r1, r2, r3, r4, r5] + [uav1, uav2, uav3, uav4, uav5]  # 所有红方单位

    # 以white_usv1为中心，组建星型网络
    engine.gen_star_network("StarNetwork4", 'white_usv1', ['white_usv2', 'white_usv3', 'white_usv4', 'white_usv1', 'white_usv5', 'white_uav1', 'white_uav2', 'white_uav3', 'white_uav4', 'white_uav5'])

    # 下一行代码多余
    reds_all = reds

    """"配置黑方USV参数"""
    engine.db["RadarWithGuider"]["distance"] = 30_000
    engine.db["RadarWithGuider"]["sector"] = [0, 360]
    engine.db["Ship"]["comdev"] = "Comdev"
    engine.db["Ship"]["emitters"] = []
    engine.db["Ship"]["guiders"] = []
    engine.db["Ship"]["motor"] = "ShipMotorTZB"
    engine.db["Ship"]["radars"] = ["RadarWithGuider"]

    b0 = engine.gen_platform('black_usv1', 'Ship', 'BLUE', black_waypoints["usv1"][0]["point"], black_waypoints["usv1"][0]["speed"], 0, coordinate_system="Cartesian")
    b1 = engine.gen_platform('black_usv2', 'Ship', 'BLUE', black_waypoints["usv2"][0]["point"], black_waypoints["usv2"][0]["speed"], 0, coordinate_system="Cartesian")
    b2 = engine.gen_platform('black_usv3', 'Ship', 'BLUE', black_waypoints["usv3"][0]["point"], black_waypoints["usv3"][0]["speed"], 0, coordinate_system="Cartesian")
    b3 = engine.gen_platform('black_usv4', 'Ship', 'BLUE', black_waypoints["usv4"][0]["point"], black_waypoints["usv4"][0]["speed"], 0, coordinate_system="Cartesian")
    b4 = engine.gen_platform('black_usv5', 'Ship', 'BLUE', black_waypoints["usv5"][0]["point"], black_waypoints["usv5"][0]["speed"], 0, coordinate_system="Cartesian")

    blues = [b0, b1, b2, b3, b4]  # 所有蓝方单位

    # 为每艘黑方USV设置航行区域（按航路点巡逻）
    engine.cmd_sail_area(b0, speed=10, xy_points=[j['point'] for j in black_waypoints['usv1']])
    engine.cmd_sail_area(b1, speed=10, xy_points=[j['point'] for j in black_waypoints['usv2']])
    engine.cmd_sail_area(b2, speed=10, xy_points=[j['point'] for j in black_waypoints['usv3']])
    engine.cmd_sail_area(b3, speed=10, xy_points=[j['point'] for j in black_waypoints['usv4']])
    engine.cmd_sail_area(b4, speed=10, xy_points=[j['point'] for j in black_waypoints['usv5']])

    """设置裁判系统"""
    all_units = reds + blues
    judge = engine.gen_judge_system("JudgeSystemTZB", all_units)
    judge_area = points_area + [points_area[0]]
    judge.set_area(judge_area)

    def start(engine):
        """仿真启动时的初始化操作"""
        engine.turn_on_radars()  
        engine.turn_on_lockers()
        uav1.uavbattery.turn_on()
        uav2.uavbattery.turn_on()
        uav3.uavbattery.turn_on()
        uav4.uavbattery.turn_on()
        uav5.uavbattery.turn_on()
        judge.activate()
        engine.put_uav_in_ship('white_uav1', 'white_usv1')
        engine.put_uav_in_ship('white_uav2', 'white_usv2')
        engine.put_uav_in_ship('white_uav3', 'white_usv3')
        engine.put_uav_in_ship('white_uav4', 'white_usv4')
        engine.put_uav_in_ship('white_uav5', 'white_usv5')
    engine.set_starter(start)

    def black_strategy(engine):
        for _b_unit in blues:
            detected_white_targets = engine.get_black_targets()
            for _w_unit_name in detected_white_targets:
                if "usv" in _w_unit_name:
                    # 下面两行代码是错的，需要改为str类型的名称
                    # _w_unit = engine.unit_by_name(_w_unit_name)
                    # engine.black_cmd_lock(_b_unit, _w_unit)
                    engine.black_cmd_lock(_b_unit.name, _w_unit_name)

    # 操作位置
    engine.add_manipulator(black_strategy, 1) # 每秒执行一次black_strategy

    # engine.cache["takeoff_flag"] = True
    # engine.cache["land_flag"] = True
    # engine.cache["change_speed_flag"] = True
    # def test_code(engine):
    #
    #     white_targets = engine.get_white_targets()
    #
    #
    #     engine.cmd_lock("white_usv2", "black_usv3")
    #     if engine.time > 1000 and engine.cache["takeoff_flag"]:
    #         engine.cmd_uav_takeoff('white_uav1', 'white_usv1', target_speed=150, target_course=90)
    #         engine.cmd_uav_takeoff('white_uav2', 'white_usv2', target_speed=150, target_course=0)
    #         engine.cmd_uav_takeoff('white_uav3', 'white_usv3', target_speed=150, target_course=0)
    #         engine.cmd_uav_takeoff('white_uav4', 'white_usv4', target_speed=150, target_course=90)
    #         engine.cmd_uav_takeoff('white_uav5', 'white_usv5', target_speed=150, target_course=0)
    #         engine.cache["takeoff_flag"] = False
    #     if alg.geo.distance(uav4.coords[:2], r4.coords[:2]) < 30_000 and engine.cache["change_speed_flag"]:
    #         uav4.motor.change_speed(19, ignore=True)
    #         engine.cache["change_speed_flag"] = False
    #     if alg.geo.distance(uav4.coords[:2], r4.coords[:2]) < 1000 and engine.cache["land_flag"]:
    #         engine.cmd_uav_land('white_uav4', 'white_usv4')
    #         engine.cache["land_flag"] = False
    #
    # engine.add_manipulator(test_code, 10)
    # time.sleep(5)

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
        engine = sim(logtag=logtag,
                     uav_speed=uav_speed)
    else:
        uav_speed = 150
        engine = sim(web_ip='127.0.0.1',
                     user_name="admin",
                     logtag="test",
                     uav_speed=uav_speed)
    engine.activate()
    engine.update()
