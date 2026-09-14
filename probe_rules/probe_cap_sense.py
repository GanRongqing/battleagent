"""综合探针: 传感语义 + 电池 + 跨船降落 (基于 faithful v6 兵力运动学)
S1: 目标离开UAV扇区后, intel(white_targets) 黏性持续多久 (雷达update_time=2s, intel雷达更新=5s)
S2: UAV失去目标后: 已有USV锁是否继续; 新锁是否仍可(黏性期内); 黏性期后新锁是否失败
S3: UAV电池耗尽(<0)是否kill; 充电速率
S4: 跨USV降落 (UAV降落非母船USV)
"""
import os, sys, random
_BASE = '/root/autodl-tmp/hsystem/hsystem'
sys.path.insert(0, _BASE + '/simserver'); sys.path.insert(0, _BASE); sys.path.insert(0, _BASE + '/simulation')
import numpy as np
import simulation.core as core

def make_engine(wships, bships, wuavs=None, buavs=None, ratio=1000):
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
    engine.db["Ship"]["motor"] = "ShipMotorTZB"; engine.db["Ship"]["radars"] = ["RadarWithGuider"]
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
            _ship = wships[i][0] if i < len(wships) else wships[0][0]
            engine.put_uav_in_ship(_n, _ship)
    engine.set_starter(start)
    return engine

def az(frm, to):
    return np.rad2deg(np.arctan2(to[0]-frm[0], to[1]-frm[1]))

# S1+S2: UAV扇区旋转走 → intel黏性 + 锁行为
random.seed(1234)
eng = make_engine(wships=[('w1',(100000,300000)),('w2',(100000,285000))],
                  bships=[('b1',(140000,300000))], wuavs=[('wuav1',(100000,300000))])
eng.activate(); eng.update(delta=12)
w1, w2, b1 = eng.unit_by_name('w1'), eng.unit_by_name('w2'), eng.unit_by_name('b1')
wuav = eng.unit_by_name('wuav1')
eng.cmd_uav_takeoff('wuav1','w1', 150, 90)
eng.update(delta=8)
print(f"[S1/S2] UAV朝{wuav.heading:.0f}° b1方位{az(wuav.coords[:2],b1.coords[:2]):.0f}° 白观测含b1={'b1' in eng.get_white_targets()[1]}")
# 先建立 w1 对 b1 的既有锁, 再把UAV转向(目标出扇区)
ok = eng.cmd_lock('w1','b1'); ok2 = eng.cmd_lock('w2','b1')
print(f"   w1锁b1={ok} w2锁b1={ok2}")
wuav.motor.set_target_angle(180); wuav.motor.set_target_speed(150)  # 转南, 扇区[150,210]
eng.update(delta=3)
print(f"   转向后UAV航向{wuav.heading:.0f}° b1方位{az(wuav.coords[:2],b1.coords[:2]):.0f}°(出[150,210])")
for i,(dt,label) in enumerate([(2,'+5s'),(5,'+10s'),(10,'+20s'),(10,'+30s'),(10,'+40s'),(30,'+70s')]):
    eng.update(delta=dt)
    sees = 'b1' in eng.get_white_targets()[1]
    print(f"   {label}: 白观测含b1={sees}  w1仍锁b1={w1.locker.locking} b1被锁={b1.locker.locked}")
eng.terminate()
print("--- S1/S2 结束")

# S3: 电池耗尽 kill + 充电
random.seed(2222)
eng = make_engine(wships=[('w1',(100000,300000))], bships=[('b1',(60000,300000))], wuavs=[('wuav1',(100000,300000))])
eng.activate(); eng.update(delta=12)
u = eng.unit_by_name('wuav1')
print(f"[S3] 总飞行时长={u.uavbattery.total_fly_time} charge_rate={u.uavbattery.charge_rate:.3f}/s")
eng.cmd_uav_takeoff('wuav1','w1', 150, 90)
eng.update(delta=100)
print(f"   起飞100s后: fly_time_remain={u.uavbattery.fly_time_remain:.1f} (期望{25000-100:.0f}) alive={u.isactive}")
# 耗尽: 把 fly_time_remain 调小观察 <0 kill
u.uavbattery.fly_time_remain = 5.0
eng.update(delta=10)
print(f"   fly_time_remain=5后+10s: remain={u.uavbattery.fly_time_remain:.1f} alive={u.isactive}  (<0→kill?)")
eng.terminate()
print("--- S3 结束")

# S4: 跨USV降落 (wuav1 母船是w1, 降落到 w2)
random.seed(3333)
eng = make_engine(wships=[('w1',(100000,300000)),('w2',(100000,300000))],
                  bships=[('b1',(60000,300000))], wuavs=[('wuav1',(100000,300000))])
eng.activate(); eng.update(delta=12)
w1, w2 = eng.unit_by_name('w1'), eng.unit_by_name('w2')
u = eng.unit_by_name('wuav1')
eng.cmd_uav_takeoff('wuav1','w1', 150, 90)
eng.update(delta=30)  # 飞离 4.5km
r = eng.cmd_uav_land('wuav1','w2')
print(f"[S4] wuav1起飞30s后(距w2≈{np.linalg.norm(np.array(u.coords[:2])-np.array(w2.coords[:2])):.0f}m) 降落w2(非母船)={r} is_at_home={u.is_at_home} w2.planes={w2.planes}")
eng.terminate()
print("--- S4 结束")
print("SENSE PROBE DONE")
