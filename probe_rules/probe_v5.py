"""探针 v5: 修正P9扇区几何(目标放入60km内) + P10黑UAV(已起飞无需takeoff) + P11互锁竞速
关键点:
- UAV雷达heading跟随"速度方向"; 悬停时冻结在_prev_course → 必须飞行
- 黑UAV由gen_platform直接生成(已在空中飞行), 不调用takeoff
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


# P9: UAV ±30°扇区跟随航向(动态) — 目标放入60km内
def p9():
    random.seed(900)
    # wuav1从(100000,300000)起飞朝东飞; b_in在ENE~72°, b_out在NE~44°, 均在55km内
    eng = make_engine(wships=[('w1', (100000, 300000))],
                      bships=[('b_in', (140000, 308000)), ('b_out', (128000, 322000))],
                      wuavs=[('wuav1', (100000, 300000))])
    eng.activate(); eng.update(delta=12)
    eng.cmd_uav_takeoff('wuav1', 'w1', 150, 90)
    eng.update(delta=8)
    wuav = eng.unit_by_name('wuav1')
    b_in, b_out = eng.unit_by_name('b_in'), eng.unit_by_name('b_out')
    a_in, a_out = az(wuav.coords[:2], b_in.coords[:2]), az(wuav.coords[:2], b_out.coords[:2])
    d_in, d_out = dist(wuav, b_in), dist(wuav, b_out)
    in_seen = 'b_in' in eng.get_white_targets()[1]
    out_seen = 'b_out' in eng.get_white_targets()[1]
    print(f"  [朝东90°] 航向{wuav.heading:.0f} 扇区[60,120]: b_in方位{a_in:.1f}°d{d_in:.0f}m可见={in_seen}"
          f"  b_out方位{a_out:.1f}°d{d_out:.0f}m可见={out_seen}")
    # 转向东北45° → 扇区[15,75]
    wuav.motor.set_target_angle(45); wuav.motor.set_target_speed(150)
    eng.update(delta=15)
    a_in2, a_out2 = az(wuav.coords[:2], b_in.coords[:2]), az(wuav.coords[:2], b_out.coords[:2])
    in2 = 'b_in' in eng.get_white_targets()[1]
    out2 = 'b_out' in eng.get_white_targets()[1]
    print(f"  [朝NE45°] 航向{wuav.heading:.0f} 扇区[15,75]: b_in方位{a_in2:.1f}°可见={in2}"
          f"  b_out方位{a_out2:.1f}°可见={out2}")
    eng.terminate()
    print("--- P9 结束")


# P10: 黑UAV(已在空中朝西飞) → 黑USV锁白 (>30km黑雷达)  [对称: 黑UAV也延长锁距]
def p10():
    for t in range(2):
        random.seed(800 + t)
        # buav1从(115000,300000)朝西飞(270) → w1在(110000,298000) SW方向∈扇区[240,300]
        # b1(75000,300000)距w1 35.5km > 30km(黑USV雷达) < 40km(锁距)
        eng = make_engine(wships=[('w1', (110000, 298000))], bships=[('b1', (75000, 300000))],
                          buavs=[('buav1', (115000, 300000))])
        eng.activate(); eng.update(delta=8)
        w1, b1 = eng.unit_by_name('w1'), eng.unit_by_name('b1')
        buav = eng.unit_by_name('buav1')
        a_w1 = az(buav.coords[:2], w1.coords[:2])
        black_sees = 'w1' in eng.get_black_targets()
        ok = eng.black_cmd_lock('b1', 'w1')
        print(f"  [t{t}] 黑UAV航向{buav.heading:.0f} w1方位{a_w1:.1f}° dist(w1,b1)={dist(w1,b1):.0f}m(>30km黑雷达)"
              f" 黑观测含w1={black_sees} 黑b1锁w1={ok}")
        eng.terminate()
    print("--- P10 结束")


# P11: 互锁竞速 — 白2v1(b1) vs 黑1v1(w1): 谁先死?
def p11():
    for t in range(3):
        random.seed(1100 + t)
        eng = make_engine(wships=[('w1', (100000, 300000)), ('w2', (100000, 285000))],
                          bships=[('b1', (130000, 300000))])
        eng.activate(); eng.update(delta=12)
        w1, w2, b1 = eng.unit_by_name('w1'), eng.unit_by_name('w2'), eng.unit_by_name('b1')
        rw1 = eng.cmd_lock('w1', 'b1'); rw2 = eng.cmd_lock('w2', 'b1')
        rb = eng.black_cmd_lock('b1', 'w1')
        print(f"  [t{t}] 白锁黑: w1={rw1} w2={rw2}  黑锁白: b1→w1={rb}")
        line = []
        for i in range(14):
            eng.update(delta=50)
            st = f"  +{(i+1)*50:4d}s b1:[hits={b1.locker.locked_times} frz={b1.locker.frozen} alive={b1.isactive}]"
            st += f" w1:[hits={w1.locker.locked_times} frz={w1.locker.frozen} alive={w1.isactive}]"
            st += f" w2:[hits={w2.locker.locked_times} frz={w2.locker.frozen}]"
            line.append(st)
        print("\n".join(line))
        eng.terminate()
    print("--- P11 结束")


if __name__ == '__main__':
    p9(); p10(); p11()
    print("V5 DONE")
