"""探针3: (1) 直接检查UAV雷达/intel轨道留存来源 (P1的~25-35s黏性到底在哪个环节)
(2) 修正后的跨USV降落 (w2在东侧8.5km, UAV低速50接近)
(3) intel完全过期后(35s+) 无锁USV新锁是否失败
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

# (1) 黏性定位
random.seed(501)
eng = make_engine(wships=[('w1',(100000,300000))], bships=[('b1',(138000,300000))], wuavs=[('wuav1',(100000,300000))])
eng.activate(); eng.update(delta=12)
w1, b1, wuav = eng.unit_by_name('w1'), eng.unit_by_name('w2') if False else eng.unit_by_name('w1'), eng.unit_by_name('wuav1')
rad = wuav.radars[0]
print(f"[STICK] radar attr: update_time={rad.attr.update_time} yield_time={rad.attr.yield_time} period={rad.attr.period} "
      f"intel radar_update_time={wuav.intelligence.attr['radar_update_time']} tick增量/秒: 测前tick={eng.tick}")
eng.cmd_uav_takeoff('wuav1','w1',150,90)
eng.update(delta=8)
print(f"  起飞8s后 UAV航向{wuav.heading:.0f}° speed={wuav.motor.real_speed:.0f} b1方位{az(wuav.coords[:2],b1.coords[:2]):.0f}° "
      f"acquire={rad.acquire(b1)} 雷达track数={len(rad._found_target_tracks)} intel track数={len(wuav.intelligence.radar_tracks)}")
wuav.motor.set_target_angle(180); wuav.motor.set_target_speed(150)
print("  转180°后 (每2s):")
for i in range(14):
    eng.update(delta=2)
    print(f"   +{(i+1)*2:2d}s hd={wuav.heading:.0f}° az_b1={az(wuav.coords[:2],b1.coords[:2]):.0f}° acquire={rad.acquire(b1)} "
          f"radTracks={len(rad._found_target_tracks)} intelTracks={len(wuav.intelligence.radar_tracks)} "
          f"white含b1={'b1' in eng.get_white_targets()[1]}")
# 黏性结束后 新锁测试
eng.update(delta=10)   # 总计~40s
ok_new = eng.cmd_lock('w1','b1')
print(f"  总~50s(intel已过期): 白含b1={'b1' in eng.get_white_targets()[1]} w1新锁b1={ok_new}")
eng.terminate()
print("--- STICK 结束")

# (2) 修正跨USV降落
random.seed(602)
eng = make_engine(wships=[('w1',(100000,300000)),('w2',(110000,300000))], bships=[('b1',(60000,300000))], wuavs=[('wuav1',(100000,300000))])
eng.activate(); eng.update(delta=12)
w1, w2, u = eng.unit_by_name('w1'), eng.unit_by_name('w2'), eng.unit_by_name('wuav1')
eng.cmd_uav_takeoff('wuav1','w1',50,90)   # 起飞即低速50朝东
eng.update(delta=30)  # ~1.5km东, 距w2 ~8.5km
print(f"[LAND] 起飞30s: 距w1={dist(u,w1):.0f}m 距w2={dist(u,w2):.0f}m speed={u.motor.real_speed:.0f} (母船=w1)")
r = eng.cmd_uav_land('wuav1','w2')
print(f"   cmd_uav_land(wuav1→w2非母船)={r} is_at_home={u.is_at_home} w2.planes含wuav1={'wuav1' in w2.planes} "
      f"w1.planes含wuav1={'wuav1' in w1.planes} home_unit={getattr(u,'home_unit',None)}")
eng.terminate()
print("--- LAND 结束")
print("SENSE3 DONE")
