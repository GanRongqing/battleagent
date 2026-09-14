"""探针 v6: 忠实复刻官方脚本的兵力运动学
- 白USV: gen(speed=10, course=90) 自行东向
- 黑USV: gen(speed=10, course=0) + cmd_sail_area(speed=10) 西向
- 黑UAV: gen(speed=uav_speed, course=0) + cmd_sail_area(speed=30) 西向 (已在空中)
- 白UAV: gen(speed=150, course=90) + put_uav_in_ship (起飞由agent命令)
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
        engine.cmd_sail_area(name, speed=10, xy_points=[[xy[0], xy[1]], [xy[0] // 2, xy[1]], [0, xy[1]]])
    engine.db["RadarWithGuider"]["distance"] = 60_000
    engine.db["RadarWithGuider"]["sector"] = [-30, 30]
    buavs = buavs or []
    for name, xy in buavs:
        engine.gen_platform(name, 'AEW', 'BLUE', list(xy), 150, 0, 100, coordinate_system="Cartesian")
        engine.cmd_sail_area(name, speed=30, xy_points=[[xy[0], xy[1]], [xy[0] // 2, xy[1]], [0, xy[1]]])
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


# P5: UAV飞行目指 → USV锁 >35km 雷达外目标
def p5():
    for t in range(3):
        random.seed(500 + t)
        eng = make_engine(wships=[('w1', (100000, 300000))], bships=[('b1', (139000, 300000))],
                          wuavs=[('wuav1', (100000, 300000))])
        eng.activate(); eng.update(delta=12)
        eng.cmd_uav_takeoff('wuav1', 'w1', 150, 90)
        eng.update(delta=8)
        w1, b1 = eng.unit_by_name('w1'), eng.unit_by_name('b1')
        white_sees = 'b1' in eng.get_white_targets()[1]
        ok = eng.cmd_lock('w1', 'b1')
        print(f"  [t{t}] dist(w1,b1)={dist(w1,b1):.0f}m(>35km雷达) UAV朝{eng.unit_by_name('wuav1').heading:.0f}° 白观测含b1={white_sees} w1锁b1={ok}")
        if ok:
            eng.update(delta=310)
            print(f"    +310s: b1 hits={b1.locker.locked_times} frozen={b1.locker.frozen} alive={b1.isactive}")
        eng.terminate()
    print("--- P5 结束")


# P6b: 纯距离脱锁机制 (锁定后瞬移>40km)
def p6b():
    for t in range(2):
        random.seed(650 + t)
        eng = make_engine(wships=[('w1', (105000, 300000))], bships=[('b1', (130000, 300000))])
        eng.activate(); eng.update(delta=12)
        w1, b1 = eng.unit_by_name('w1'), eng.unit_by_name('b1')
        ok = eng.black_cmd_lock('b1', 'w1')
        print(f"  [t{t}] 黑b1锁w1={ok} dist={dist(w1,b1):.0f}m w1被锁={w1.locker.locked}")
        w1.coords[:] = [175000, 300000, 0]
        eng.update(delta=5)
        print(f"    瞬移后 dist={dist(w1,b1):.0f}m w1被锁={w1.locker.locked} b1.locking={b1.locker.locking}")
        eng.terminate()
    print("--- P6b 结束")


# P9: UAV ±30°扇区跟随航向 (用 acquire 直测实时扇区; white_targets 观察30s黏性)
def p9():
    random.seed(900)
    eng = make_engine(wships=[('w1', (100000, 300000))],
                      bships=[('b_in', (140000, 308000)), ('b_out', (128000, 322000))],
                      wuavs=[('wuav1', (100000, 300000))])
    eng.activate(); eng.update(delta=12)
    eng.cmd_uav_takeoff('wuav1', 'w1', 150, 90)
    eng.update(delta=8)
    wuav = eng.unit_by_name('wuav1')
    b_in, b_out = eng.unit_by_name('b_in'), eng.unit_by_name('b_out')
    rad = wuav.radars[0]
    a_in, a_out = az(wuav.coords[:2], b_in.coords[:2]), az(wuav.coords[:2], b_out.coords[:2])
    print(f"  [朝东90 扇区[60,120]] b_in az{a_in:.0f}° acquire={rad.acquire(b_in)}  b_out az{a_out:.0f}° acquire={rad.acquire(b_out)}"
          f"  white含b_in={'b_in' in eng.get_white_targets()[1]}")
    wuav.motor.set_target_angle(45); wuav.motor.set_target_speed(150)
    eng.update(delta=15)
    a_in2, a_out2 = az(wuav.coords[:2], b_in.coords[:2]), az(wuav.coords[:2], b_out.coords[:2])
    print(f"  [朝NE45 扇区[15,75]] b_in az{a_in2:.0f}° acquire={rad.acquire(b_in)}  b_out az{a_out2:.0f}° acquire={rad.acquire(b_out)}")
    # 黏性: 等31s让intel过期, 再查white_targets
    eng.update(delta=31)
    print(f"  转向45°后+31s(扇形外目标intel过期): white含b_in={'b_in' in eng.get_white_targets()[1]} 含b_out={'b_out' in eng.get_white_targets()[1]}")
    eng.terminate()
    print("--- P9 结束")


# P10: 黑UAV(空中朝西飞, 30m/s) → 黑USV锁白 (>30km黑雷达)
def p10():
    for t in range(2):
        random.seed(800 + t)
        # buav1(115km,300km)朝西飞(经路点), w1(110km,298km)在SW方位∈[240,300]; b1(75km,300km)距w1 35.5km
        eng = make_engine(wships=[('w1', (110000, 298000))], bships=[('b1', (75000, 300000))],
                          buavs=[('buav1', (115000, 300000))])
        eng.activate(); eng.update(delta=8)
        w1, b1 = eng.unit_by_name('w1'), eng.unit_by_name('b1')
        buav = eng.unit_by_name('buav1')
        a_w1 = az(buav.coords[:2], w1.coords[:2])
        black_sees = 'w1' in eng.get_black_targets()
        ok = eng.black_cmd_lock('b1', 'w1')
        print(f"  [t{t}] 黑UAV航向{buav.heading:.0f}°速度{buav.motor.real_speed:.0f} w1方位{a_w1:.1f}° dist(w1,b1)={dist(w1,b1):.0f}m(>30km黑雷达)"
              f" 黑观测含w1={black_sees} 黑b1锁w1={ok}")
        eng.terminate()
    print("--- P10 结束")


# P11: 互锁竞速 — 白2v1(b1) vs 黑1v1(w1), 黑b1能看到w1(25km)
def p11():
    for t in range(3):
        random.seed(1100 + t)
        eng = make_engine(wships=[('w1', (105000, 300000)), ('w2', (100000, 285000))],
                          bships=[('b1', (130000, 300000))])
        eng.activate(); eng.update(delta=12)
        w1, w2, b1 = eng.unit_by_name('w1'), eng.unit_by_name('w2'), eng.unit_by_name('b1')
        rw1 = eng.cmd_lock('w1', 'b1'); rw2 = eng.cmd_lock('w2', 'b1')
        rb = eng.black_cmd_lock('b1', 'w1')
        print(f"  [t{t}] 白锁黑 w1={rw1} w2={rw2}  黑锁白 b1→w1={rb}")
        for i in range(14):
            eng.update(delta=50)
            print(f"    +{(i+1)*50:4d}s b1[hits={b1.locker.locked_times} frz={b1.locker.frozen} alive={b1.isactive}] "
                  f"w1[hits={w1.locker.locked_times} frz={w1.locker.frozen} alive={w1.isactive}] "
                  f"w2[hits={w2.locker.locked_times} frz={w2.locker.frozen}]")
        eng.terminate()
    print("--- P11 结束")


if __name__ == '__main__':
    p5(); p6b(); p9(); p10(); p11()
    print("V6 DONE")
