"""探针2: 隔离4个未定项
P1 纯intel黏性(无锁): b1在UAV扇区→UAV转头→white_targets何时丢b1 (期望~5-7s)
P2 锁后目标丢失: 既有锁是否持续 + 另一USV可否新锁同一目标(共享intel/锁定目标)
P3 电池<0 kill: 篡改take_off_time→fly_time_remain<0→kill
P4 跨USV低速降落: 非母船USV, UAV speed<100, cmd_uav_land
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
def az(frm, to):
    return np.rad2deg(np.arctan2(to[0]-frm[0], to[1]-frm[1]))

# P1 纯intel黏性
random.seed(101)
eng = make_engine(wships=[('w1',(100000,300000))], bships=[('b1',(138000,300000))], wuavs=[('wuav1',(100000,300000))])
eng.activate(); eng.update(delta=12)
w1, b1, wuav = eng.unit_by_name('w1'), eng.unit_by_name('b1'), eng.unit_by_name('wuav1')
eng.cmd_uav_takeoff('wuav1','w1',150,90)
eng.update(delta=8)
print(f"[P1] w1→b1={dist(w1,b1):.0f}m(>35km雷达) UAV航向{wuav.heading:.0f}° b1方位{az(wuav.coords[:2],b1.coords[:2]):.0f}° 白含b1={'b1' in eng.get_white_targets()[1]}")
wuav.motor.set_target_angle(180); wuav.motor.set_target_speed(150)
print("    UAV转180°(b1出[150,210]扇区):")
for dt, label in [(1,'+1s'),(1,'+2s'),(3,'+5s'),(2,'+7s'),(3,'+10s'),(5,'+15s'),(10,'+25s'),(10,'+35s')]:
    eng.update(delta=dt)
    sees = 'b1' in eng.get_white_targets()[1]
    print(f"    {label}: 白含b1={sees}  (b1方位{az(wuav.coords[:2],b1.coords[:2]):.0f}°)")
eng.terminate()
print("--- P1 结束")

# P2 锁后目标丢失 + 共享新锁
random.seed(202)
eng = make_engine(wships=[('w1',(100000,300000)),('w2',(100000,286000))], bships=[('b1',(132000,300000))], wuavs=[('wuav1',(100000,300000))])
eng.activate(); eng.update(delta=12)
w1, w2, b1, wuav = eng.unit_by_name('w1'), eng.unit_by_name('w2'), eng.unit_by_name('b1'), eng.unit_by_name('wuav1')
eng.cmd_uav_takeoff('wuav1','w1',150,90)
eng.update(delta=8)
print(f"[P2] w1→b1={dist(w1,b1):.0f}m w2→b1={dist(w2,b1):.0f}m UAV航向{wuav.heading:.0f}° b1方位{az(wuav.coords[:2],b1.coords[:2]):.0f}°")
ok1 = eng.cmd_lock('w1','b1'); ok2 = eng.cmd_lock('w2','b1')
print(f"    白含b1={'b1' in eng.get_white_targets()[1]} w1锁b1={ok1} w2锁b1={ok2} b1.locked={b1.locker.locked} 链数={len(b1.locker.locked_info)}")
wuav.motor.set_target_angle(180); wuav.motor.set_target_speed(150)
eng.update(delta=15)
print(f"    UAV转180°+15s(UAV不再见b1): 白含b1={'b1' in eng.get_white_targets()[1]}(锁保) w1仍锁={w1.locker.locking} b1.locked={b1.locker.locked} 链数={len(b1.locker.locked_info)}")
eng.update(delta=300)
print(f"    +300s: b1 hits={b1.locker.locked_times} w1锁={w1.locker.locking} w2锁={w2.locker.locking} b1.locked={b1.locker.locked} 链数={len(b1.locker.locked_info)}")
eng.terminate()
print("--- P2 结束")

# P3 电池<0 kill
random.seed(303)
eng = make_engine(wships=[('w1',(100000,300000))], bships=[('b1',(60000,300000))], wuavs=[('wuav1',(100000,300000))])
eng.activate(); eng.update(delta=12)
u = eng.unit_by_name('wuav1')
eng.cmd_uav_takeoff('wuav1','w1',150,90)
eng.update(delta=5)
print(f"[P3] 起飞后 remain={u.uavbattery.fly_time_remain:.0f} alive={u.isactive} take_off_time={u.take_off_time} 当前t={eng.time:.0f}")
# 模拟飞行了25050s → remain<0
u.take_off_time = eng.time - 25050
eng.update(delta=3)
print(f"    篡改take_off_time→remain={u.uavbattery.fly_time_remain:.0f} alive={u.isactive} (负→kill) w1.planes仍含uav?={'wuav1' in w1.planes if False else u.is_at_home}")
eng.terminate()
print("--- P3 结束")

# P4 跨USV低速降落
random.seed(404)
eng = make_engine(wships=[('w1',(100000,300000)),('w2',(100000,300000))], bships=[('b1',(60000,300000))], wuavs=[('wuav1',(100000,300000))])
eng.activate(); eng.update(delta=12)
w1, w2, u = eng.unit_by_name('w1'), eng.unit_by_name('w2'), eng.unit_by_name('wuav1')
eng.cmd_uav_takeoff('wuav1','w1',150,90)
eng.update(delta=30)  # 距w1约4.5km
print(f"[P4] 起飞30s: wuav距w1={dist(u,w1):.0f}m 距w2={dist(u,w2):.0f}m speed={u.motor.real_speed:.0f}")
# 减速到50, 朝w2飞近
eng.cmd_uav_takeoff('wuav1','w1',50,90)
eng.update(delta=60)
r = eng.cmd_uav_land('wuav1','w2')
print(f"    +60s(朝w2, speed={u.motor.real_speed:.0f}): 距w2={dist(u,w2):.0f}m 降落w2(非母船)={r} is_at_home={u.is_at_home} w2.planes={len(w2.planes)}")
eng.terminate()
print("--- P4 结束")
print("SENSE2 DONE")
