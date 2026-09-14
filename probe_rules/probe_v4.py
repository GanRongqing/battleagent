"""探针 v4: 修正 UAV 目指 / 规避几何 / 扇区
关键修复: UAV radar 的 heading 跟随"速度方向"(course), 不是指令角 real_angle.
悬停(speed=0)时 heading 冻结在 _prev_course(初始0=北) → 必须让UAV飞起来.
"""
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
    for name, xy in buavs: engine.gen_platform(name, 'AEW', 'BLUE', list(xy), 0, 270, 100, coordinate_system="Cartesian")
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


def az(frm, to):
    return np.rad2deg(np.arctan2(to[0] - frm[0], to[1] - frm[1]))


# P5: UAV起飞飞行(朝东) → 白方观测 b1(>35km) → w1 锁 39km 目标 (超自身雷达锁定)
def p5():
    for t in range(3):
        random.seed(500 + t)
        eng = make_engine(wships=[('w1', (100000, 300000))], bships=[('b1', (139000, 300000))],
                          wuavs=[('wuav1', (100000, 300000))])
        eng.activate(); eng.update(delta=12)
        r = eng.cmd_uav_takeoff('wuav1', 'w1', 150, 90)   # 朝东飞
        eng.update(delta=8)
        w1, b1 = eng.unit_by_name('w1'), eng.unit_by_name('b1')
        uav = eng.unit_by_name('wuav1')
        white_sees = 'b1' in eng.get_white_targets()[1]
        dw = dist(w1, b1)
        print(f"  [t{t}] 起飞={r} UAV朝{eng.unit_by_name('wuav1').heading:.0f}° dist(w1,b1)={dw:.0f}m(>35km) 白观测含b1={white_sees}")
        ok = eng.cmd_lock('w1', 'b1')
        print(f"    w1锁b1 = {ok}  (UAV目指→USV锁超自身雷达目标)")
        if ok:
            eng.update(delta=310)
            print(f"    +310s: b1 hits={b1.locker.locked_times} frozen={b1.locker.frozen}")
        eng.terminate()
    print("--- P5 结束")


# P6: 被锁后能否靠"拉开距离"脱锁? (黑b1锁w1, w1东逃) + P6b: 纯距离机制(瞬移>40km)
def p6():
    for t in range(3):
        random.seed(600 + t)
        # b1在西(105km), w1在东(120km), 距离15km < 黑雷达30km
        eng = make_engine(wships=[('w1', (120000, 300000))], bships=[('b1', (105000, 300000))])
        eng.activate(); eng.update(delta=12)
        w1, b1 = eng.unit_by_name('w1'), eng.unit_by_name('b1')
        black_sees = 'w1' in eng.get_black_targets()
        ok = eng.black_cmd_lock('b1', 'w1')
        print(f"  [t{t}] 黑观测含w1={black_sees} 黑b1锁w1={ok} dist={dist(w1,b1):.0f}m")
        # w1 向东逃 (b1在西侧), 相对20m/s (真实游戏中黑船向西航行10, 相对仅10m/s)
        w1.motor.set_target_angle(90); w1.motor.set_target_speed(20)
        for dt, lbl in [(290, '+290s(roll前)'), (20, '+310s(roll后)'), (300, '+610s'), (600, '+1210s')]:
            eng.update(delta=dt)
            print(f"    {lbl}: dist={dist(w1,b1):.0f}m 被锁={w1.locker.locked} hits={w1.locker.locked_times} frozen={w1.locker.frozen}")
        eng.terminate()
    print("--- P6 结束")


def p6b():
    # 纯距离机制: 锁定后立刻瞬移目标>40km, 观察 _locking_work 清锁 (避开300s roll)
    for t in range(2):
        random.seed(650 + t)
        eng = make_engine(wships=[('w1', (120000, 300000))], bships=[('b1', (105000, 300000))])
        eng.activate(); eng.update(delta=12)
        w1, b1 = eng.unit_by_name('w1'), eng.unit_by_name('b1')
        ok = eng.black_cmd_lock('b1', 'w1')
        print(f"  [t{t}] 锁={ok} dist={dist(w1,b1):.0f}m w1被锁={w1.locker.locked}")
        w1.coords[:] = [160000, 300000, 0]   # 瞬移: 距离→55km
        eng.update(delta=5)
        print(f"    瞬移后 dist={dist(w1,b1):.0f}m w1被锁={w1.locker.locked} b1.locking={b1.locker.locking}")
        eng.terminate()
    print("--- P6b 结束")


# P9: UAV ±30°扇区跟随航向 (飞行动态)
def p9():
    random.seed(900)
    eng = make_engine(wships=[('w1', (100000, 300000))],
                      bships=[('b_in', (160000, 315000)), ('b_out', (150000, 340000))],
                      wuavs=[('wuav1', (100000, 300000))])
    eng.activate(); eng.update(delta=12)
    eng.cmd_uav_takeoff('wuav1', 'w1', 150, 90)   # 朝东飞
    eng.update(delta=8)
    wuav = eng.unit_by_name('wuav1')
    a_in = az(wuav.coords[:2], eng.unit_by_name('b_in').coords[:2])
    a_out = az(wuav.coords[:2], eng.unit_by_name('b_out').coords[:2])
    in_seen = 'b_in' in eng.get_white_targets()[1]
    out_seen = 'b_out' in eng.get_white_targets()[1]
    print(f"  [t0] UAV航向{wuav.heading:.0f}° 扇区[{wuav.heading-30:.0f},{wuav.heading+30}]: "
          f"b_in方位{a_in:.1f}°(dist~64km)可见={in_seen}   b_out方位{a_out:.1f}°(dist~51km)可见={out_seen}")
    # 转向东北45°飞行 → 扇区[15,75]
    wuav.motor.set_target_angle(45)
    eng.update(delta=15)
    a_in2 = az(wuav.coords[:2], eng.unit_by_name('b_in').coords[:2])
    a_out2 = az(wuav.coords[:2], eng.unit_by_name('b_out').coords[:2])
    in2 = 'b_in' in eng.get_white_targets()[1]
    out2 = 'b_out' in eng.get_white_targets()[1]
    print(f"    转向后航向{wuav.heading:.0f}° 扇区[{wuav.heading-30:.0f},{wuav.heading+30}]: "
          f"b_in方位{a_in2:.1f}°可见={in2}   b_out方位{a_out2:.1f}°可见={out2}")
    eng.terminate()
    print("--- P9 结束")


# P10: 黑UAV目指 → 黑USV锁白 (>30km 黑雷达外)  [对称验证: 敌方UAV也能延长锁距]
def p10():
    for t in range(2):
        random.seed(800 + t)
        # w1(110km,306km), b1(75km,300km) → dist 35.5km > 30km(黑雷达) <40km(锁距)
        # buav1(121km,300km) 朝西飞(270), 扇区[240,300]; w1相对buav1方位~298° ∈ [240,300]
        eng = make_engine(wships=[('w1', (110000, 306000))], bships=[('b1', (75000, 300000))],
                          buavs=[('buav1', (121000, 300000))])
        eng.activate(); eng.update(delta=12)
        eng.cmd_uav_takeoff('buav1', 'b1', 150, 270)   # 黑UAV朝西飞
        eng.update(delta=8)
        w1, b1 = eng.unit_by_name('w1'), eng.unit_by_name('b1')
        buav = eng.unit_by_name('buav1')
        a_w1 = az(buav.coords[:2], w1.coords[:2])
        black_sees = 'w1' in eng.get_black_targets()
        ok = eng.black_cmd_lock('b1', 'w1')
        print(f"  [t{t}] 黑UAV航向{buav.heading:.0f}° w1相对方位{a_w1:.1f}° dist(w1,b1)={dist(w1,b1):.0f}m(>30km黑雷达) "
              f"黑观测含w1={black_sees} 黑b1锁w1={ok}")
        eng.terminate()
    print("--- P10 结束")


if __name__ == '__main__':
    p5(); p6(); p6b(); p9(); p10()
    print("V4 DONE")
