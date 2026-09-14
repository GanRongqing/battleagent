"""探针 v3: 修正 UAV 目指 / 规避几何 / 扇区 """
import os, sys, random
_BASE = '/root/autodl-tmp/hsystem/hsystem'
sys.path.insert(0, _BASE + '/simserver'); sys.path.insert(0, _BASE); sys.path.insert(0, _BASE + '/simulation')
import numpy as np
import simulation.core as core

def make_engine(wships, bships, wuavs=None, buavs=None, ratio=1000):
    engine = core.tzb_engine.TzbEngine('probe', flag=core.log.INFO, terminal=False, logtag='probe', cache=False)
    engine.set_ratio(ratio); engine.set_end_time(3600)
    big = [(-100000, -200000), (500000, -200000), (500000, 900000), (-100000, 900000)]
    engine.db["RadarWithGuider"]["distance"] = 35_000
    engine.db["RadarWithGuider"]["sector"] = [0, 360]
    engine.db["RadarWithGuider"]["detected_method"] = "fixed"
    engine.db["Ship"]["motor"] = "ShipMotorTZB"; engine.db["Ship"]["radars"] = ["RadarWithGuider"]
    for name, xy in wships: engine.gen_platform(name, 'Ship', 'RED', list(xy), 0, 90, coordinate_system="Cartesian")
    engine.db["RadarWithGuider"]["distance"] = 60_000
    engine.db["RadarWithGuider"]["sector"] = [-30, 30]
    engine.db["PlaneMotorTZB"]["max_speed"] = 150
    engine.db["AEW"]["motor"] = "PlaneMotorTZB"; engine.db["AEW"]["radars"] = ["RadarWithGuider"]
    wuavs = wuavs or []
    for name, xy in wuavs: engine.gen_platform(name, 'AEW', 'RED', list(xy), 0, 90, 100, coordinate_system="Cartesian")
    engine.db["RadarWithGuider"]["distance"] = 30_000
    engine.db["RadarWithGuider"]["sector"] = [0, 360]
    engine.db["Ship"]["motor"] = "ShipMotorTZB"; engine.db["Ship"]["radars"] = ["RadarWithGuider"]
    for name, xy in bships: engine.gen_platform(name, 'Ship', 'BLUE', list(xy), 0, 0, coordinate_system="Cartesian")
    engine.db["RadarWithGuider"]["distance"] = 60_000
    engine.db["RadarWithGuider"]["sector"] = [-30, 30]
    buavs = buavs or []
    for name, xy in buavs: engine.gen_platform(name, 'AEW', 'BLUE', list(xy), 0, 0, 100, coordinate_system="Cartesian")
    all_units = [engine.unit_by_name(n) for n, _ in wships + bships + wuavs + buavs]
    judge = engine.gen_judge_system("JudgeSystemTZB", all_units)
    judge.set_area(big + [big[0]])
    def start(engine):
        engine.turn_on_radars(); engine.turn_on_lockers()
        for _n, _xy in wuavs: engine.unit_by_name(_n).uavbattery.turn_on()
        for _n, _xy in buavs: engine.unit_by_name(_n).uavbattery.turn_on()
        judge.activate()
        for i, (_n, _xy) in enumerate(wuavs):
            _ship = wships[i][0] if i < len(wships) else wships[0][0]
            engine.put_uav_in_ship(_n, _ship)
    engine.set_starter(start)
    return engine

def dist(u1, u2):
    return np.linalg.norm(np.array(u1.coords[:2]) - np.array(u2.coords[:2]))

# P5: UAV起飞后目指 → USV锁 39km(>自身35km雷达) 目标
def p5():
    for t in range(3):
        random.seed(500 + t)
        eng = make_engine(wships=[('w1',(100000,300000))], bships=[('b1',(139000,300000))],
                          wuavs=[('wuav1',(100000,300000))])
        eng.activate(); eng.update(delta=12)
        # 起飞UAV (母船w1, 朝东90, 悬停)
        r = eng.cmd_uav_takeoff('wuav1','w1', 0, 90)
        eng.update(delta=8)
        w1, b1 = eng.unit_by_name('w1'), eng.unit_by_name('b1')
        uav = eng.unit_by_name('wuav1')
        white_sees = 'b1' in eng.get_white_targets()[1]
        print(f"  [t{t}] 起飞={r} UAV@{tuple(round(c) for c in uav.coords[:2])} dist(w1,b1)={dist(w1,b1):.0f}m 白观测含b1={white_sees}")
        ok = eng.cmd_lock('w1','b1')
        print(f"    w1锁b1={ok}")
        if ok:
            eng.update(delta=310)
            print(f"    +310s: b1 hits={b1.locker.locked_times} frozen={b1.locker.frozen}")
        eng.terminate()
    print("--- P5 结束")

# P6: 黑UAV目指锁白(40km附近) + 白东逃 → 验证脱离40km解锁
def p6():
    random.seed(600)
    # buav1 在w1东侧面向西; b1在w1西侧35km
    eng = make_engine(wships=[('w1',(140000,300000))], bships=[('b1',(105000,300000))],
                      buavs=[('buav1',(150000,300000))])
    eng.activate(); eng.update(delta=12)
    buav = eng.unit_by_name('buav1'); buav.motor.set_target_angle(270)
    eng.update(delta=5)
    w1, b1 = eng.unit_by_name('w1'), eng.unit_by_name('b1')
    black_sees = 'w1' in eng.get_black_targets()
    ok = eng.black_cmd_lock('b1','w1')
    print(f"  [t0] 黑观测含w1={black_sees} 黑锁白={ok} dist={dist(w1,b1):.0f} w1被锁={w1.locker.locked}")
    # 白向东逃 (b1在w1西105km? 不, b1在105000, w1在140000 → 35km, b1在西侧)
    w1.motor.set_target_angle(90); w1.motor.set_target_speed(20)
    for dt, label in [(100,'+100'),(100,'+200'),(100,'+300'),(100,'+400')]:
        eng.update(delta=dt)
        print(f"    {label}: dist={dist(w1,b1):.0f} w1被锁={w1.locker.locked} w1被命中={w1.locker.locked_times}")
    eng.terminate()
    print("--- P6 结束")

# P9: UAV ±30°扇区 (目标放x>60000避开突防线)
def p9():
    random.seed(900)
    eng = make_engine(wships=[('w1',(100000,300000))],
                      bships=[('b_in',(160000,315000)),('b_out',(150000,340000))],
                      wuavs=[('wuav1',(100000,300000))])
    eng.activate(); eng.update(delta=12)
    eng.cmd_uav_takeoff('wuav1','w1', 0, 90)   # 朝东, 扇区[60,120]
    eng.update(delta=8)
    wuav = eng.unit_by_name('wuav1')
    az_in = np.rad2deg(np.arctan2(160000-100000, 315000-300000))  # atan2(x,y)
    az_out = np.rad2deg(np.arctan2(150000-100000, 340000-300000))
    in_seen = 'b_in' in eng.get_white_targets()[1]
    out_seen = 'b_out' in eng.get_white_targets()[1]
    print(f"  [t0] UAV朝东90°扇区[60,120]: b_in方位{az_in:.1f}可见={in_seen}   b_out方位{az_out:.1f}可见={out_seen}")
    # 让UAV转头朝东北45°, 扇区[15,75]
    wuav.motor.set_target_angle(45)
    eng.update(delta=12)
    az_in2 = np.rad2deg(np.arctan2(160000-100000, 315000-300000))
    in2 = 'b_in' in eng.get_white_targets()[1]
    print(f"    UAV朝45°扇区[15,75]: b_in方位{az_in2:.1f}可见={in2}")
    eng.terminate()
    print("--- P9 结束")

# P10: 黑UAV目指 → 黑USV锁白(35km>黑雷达30km)
def p10():
    for t in range(2):
        random.seed(800 + t)
        # buav1在w1东侧面向西, w1在140k, b1在105k(35km>30km黑雷达)
        eng = make_engine(wships=[('w1',(140000,300000))], bships=[('b1',(105000,300000))],
                          buavs=[('buav1',(150000,300000))])
        eng.activate(); eng.update(delta=12)
        buav = eng.unit_by_name('buav1'); buav.motor.set_target_angle(270)
        eng.update(delta=5)
        w1, b1 = eng.unit_by_name('w1'), eng.unit_by_name('b1')
        black_sees = 'w1' in eng.get_black_targets()
        ok = eng.black_cmd_lock('b1','w1')
        print(f"  [t{t}] 黑观测含w1={black_sees} dist={dist(w1,b1):.0f}m 黑b1锁w1={ok}")
        eng.terminate()
    print("--- P10 结束")

if __name__ == '__main__':
    p5(); p6(); p9(); p10()
    print("V3 DONE")
