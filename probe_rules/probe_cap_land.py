"""跨USV降落 (修正版): w2在东侧10km, UAV低速50朝东, 30s后距w2~8.5km, cmd_uav_land到非母船w2
另: 低空起飞/降落时 is_at_home/battery充电 语义
"""
import os, sys, random
_BASE = '/root/autodl-tmp/hsystem/hsystem'
sys.path.insert(0, _BASE + '/simserver'); sys.path.insert(0, _BASE); sys.path.insert(0, _BASE + '/simulation')
import numpy as np
import simulation.core as core

def make_engine(wships, bships, wuavs=None, ratio=1000):
    engine = core.tzb_engine.TzbEngine('probe', flag=core.log.INFO, terminal=False, logtag='probe', cache=False)
    engine.set_ratio(ratio); engine.set_end_time(600000)
    big = [(-100000, -200000), (500000, -200000), (500000, 900000), (-100000, 900000)]
    engine.db["RadarWithGuider"]["distance"] = 35_000
    engine.db["RadarWithGuider"]["sector"] = [0, 360]
    engine.db["RadarWithGuider"]["detected_method"] = "fixed"
    engine.db["Ship"]["motor"] = "ShipMotorTZB"; engine.db["Ship"]["radars"] = ["RadarWithGuider"]
    for name, xy in wships: engine.gen_platform(name, 'Ship', 'RED', list(xy), 10, 90, coordinate_system="Cartesian")
    engine.db["RadarWithGuider"]["distance"] = 60_000
    engine.db["RadarWithGuider"]["sector"] = [-30, 30]
    engine.db["PlaneMotorTZB"]["max_speed"] = 150
    engine.db["AEW"]["motor"] = "PlaneMotorTZB"; engine.db["AEW"]["radars"] = ["RadarWithGuider"]
    wuavs = wuavs or []
    for name, xy in wuavs: engine.gen_platform(name, 'AEW', 'RED', list(xy), 150, 90, 100, coordinate_system="Cartesian")
    engine.db["RadarWithGuider"]["distance"] = 30_000
    engine.db["RadarWithGuider"]["sector"] = [0, 360]
    for name, xy in bships:
        engine.gen_platform(name, 'Ship', 'BLUE', list(xy), 10, 0, coordinate_system="Cartesian")
        engine.cmd_sail_area(name, speed=10, xy_points=[[xy[0], xy[1]], [xy[0]//2, xy[1]], [0, xy[1]]])
    all_units = [engine.unit_by_name(n) for n, _ in wships + bships + wuavs]
    judge = engine.gen_judge_system("JudgeSystemTZB", all_units)
    judge.set_area(big + [big[0]])
    def start(engine):
        engine.turn_on_radars(); engine.turn_on_lockers()
        for _n, _xy in wuavs: engine.unit_by_name(_n).uavbattery.turn_on()
        judge.activate()
        for i, (_n, _xy) in enumerate(wuavs):
            engine.put_uav_in_ship(_n, wships[i][0])
    engine.set_starter(start)
    return engine

def dist(a, b):
    return np.linalg.norm(np.array(a.coords[:2]) - np.array(b.coords[:2]))

random.seed(602)
eng = make_engine(wships=[('w1',(100000,300000)),('w2',(110000,300000))], bships=[('b1',(60000,300000))], wuavs=[('wuav1',(100000,300000))])
eng.activate(); eng.update(delta=12)
w1, w2, u = eng.unit_by_name('w1'), eng.unit_by_name('w2'), eng.unit_by_name('wuav1')
eng.cmd_uav_takeoff('wuav1','w1',50,90)
eng.update(delta=30)
print(f"[LAND] 起飞30s: 距w1={dist(u,w1):.0f}m 距w2={dist(u,w2):.0f}m speed={u.motor.real_speed:.0f} is_at_home={u.is_at_home} home_unit={u.home_unit.name if u.home_unit else None}")
r = eng.cmd_uav_land('wuav1','w2')
print(f"   cmd_uav_land(wuav1→w2, 非母船)={r}")
eng.update(delta=2)
print(f"   +2s: is_at_home={u.is_at_home} 在w2={ 'wuav1' in w2.planes} 在w1={'wuav1' in w1.planes} "
      f"home_unit={u.home_unit.name if u.home_unit else None} battery_charging={u.uavbattery.is_charging} "
      f"uav_radar_on={u.radars[0].is_on}")
# 回到w1/再起飞确认同一UAV可复用
eng.cmd_uav_takeoff('wuav1','w2',50,90)
eng.update(delta=5)
print(f"   再起飞(从w2): 成功, is_at_home={u.is_at_home} w2.planes={len(w2.planes)}")
eng.terminate()
print("--- LAND 结束")
