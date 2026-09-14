"""短时机制探针 v2 (不修改simulator, 不跑长仿真)"""
import os, sys, random
_BASE = '/root/autodl-tmp/hsystem/hsystem'
sys.path.insert(0, _BASE + '/simserver')
sys.path.insert(0, _BASE)
sys.path.insert(0, _BASE + '/simulation')
import numpy as np
import simulation.core as core

RATIO = 1000

def make_engine(wships, bships, wuavs=None, buavs=None, ratio=RATIO):
    engine = core.tzb_engine.TzbEngine('probe', flag=core.log.INFO, terminal=False, logtag='probe', cache=False)
    engine.set_ratio(ratio); engine.set_end_time(3600)
    big = [(-100000, -200000), (500000, -200000), (500000, 900000), (-100000, 900000)]
    engine.db["RadarWithGuider"]["distance"] = 35_000
    engine.db["RadarWithGuider"]["sector"] = [0, 360]
    engine.db["RadarWithGuider"]["detected_method"] = "fixed"
    engine.db["Ship"]["motor"] = "ShipMotorTZB"
    engine.db["Ship"]["radars"] = ["RadarWithGuider"]
    for name, xy in wships:
        engine.gen_platform(name, 'Ship', 'RED', list(xy), 0, 90, coordinate_system="Cartesian")
    engine.db["RadarWithGuider"]["distance"] = 60_000
    engine.db["RadarWithGuider"]["sector"] = [-30, 30]
    engine.db["PlaneMotorTZB"]["max_speed"] = 150
    engine.db["AEW"]["motor"] = "PlaneMotorTZB"
    engine.db["AEW"]["radars"] = ["RadarWithGuider"]
    wuavs = wuavs or []
    for name, xy in wuavs:
        engine.gen_platform(name, 'AEW', 'RED', list(xy), 0, 90, 100, coordinate_system="Cartesian")
    engine.db["RadarWithGuider"]["distance"] = 30_000
    engine.db["RadarWithGuider"]["sector"] = [0, 360]
    engine.db["Ship"]["motor"] = "ShipMotorTZB"
    engine.db["Ship"]["radars"] = ["RadarWithGuider"]
    for name, xy in bships:
        engine.gen_platform(name, 'Ship', 'BLUE', list(xy), 0, 0, coordinate_system="Cartesian")
    engine.db["RadarWithGuider"]["distance"] = 60_000
    engine.db["RadarWithGuider"]["sector"] = [-30, 30]
    buavs = buavs or []
    for name, xy in buavs:
        engine.gen_platform(name, 'AEW', 'BLUE', list(xy), 0, 0, 100, coordinate_system="Cartesian")
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

def run(title, fn, trials=1):
    print(f"\n### {title}")
    for t in range(trials):
        fn(t)
    print(f"--- {title} 结束")

# P1: 2v1同锁 → 300s窗口命中分布 (12次)
def p1():
    def one(t):
        random.seed(100 + t)
        eng = make_engine(wships=[('w1',(100000,300000)),('w2',(100000,283000))], bships=[('b1',(130000,300000))])
        eng.activate(); eng.update(delta=12)  # 等雷达出点
        b1 = eng.unit_by_name('b1')
        t0 = eng.time
        eng.cmd_lock('w1','b1'); eng.cmd_lock('w2','b1')
        eng.update(delta=300)  # locked_time≈300, 未roll
        print(f"  [seed{t}] t0={t0:.0f} +300s(locked_time≈300): hits={b1.locker.locked_times} frozen={b1.locker.frozen} alive={b1.isactive}")
        eng.update(delta=10)   # 超过300 → roll
        print(f"          +310s: hits={b1.locker.locked_times} frozen={b1.locker.frozen} alive={b1.isactive}")
        eng.terminate()
    run("P1: 2v1同锁300s窗口 (12次, 期望64%双hit击杀)", one, trials=12)

# P2: 1v1 命中/冻结/重锁节奏
def p2():
    def one(t):
        random.seed(200 + t)
        eng = make_engine(wships=[('w1',(100000,300000))], bships=[('b1',(130000,300000))])
        eng.activate(); eng.update(delta=12)
        b1 = eng.unit_by_name('b1'); w1 = eng.unit_by_name('w1')
        eng.cmd_lock('w1','b1')
        eng.update(delta=310)  # locked_time≈298? 不: t0=12, +310 → 322, locked=310>300 → roll已发生
        h1 = b1.locker.locked_times
        print(f"  [seed{t}] +310s: hits={h1} frozen={b1.locker.frozen} w1.locking={w1.locker.locking} (锁定中hits1=命中→冻结)")
        if h1 >= 1:
            eng.cmd_lock('w1','b1')   # 冻结中重锁(可能失败, 目标frozen仍targetable?)
            eng.update(delta=300)
            print(f"    冻结中重锁+300s: hits={b1.locker.locked_times} frozen={b1.locker.frozen} alive={b1.isactive}")
            eng.update(delta=20)
            print(f"    +320s: hits={b1.locker.locked_times} alive={b1.isactive}")
        else:
            # miss → 链断+攻击者释放; 重锁应成功并开新周期
            r1 = eng.cmd_lock('w1','b1')
            eng.update(delta=305)
            print(f"    miss→重锁={r1} 再+305s: hits={b1.locker.locked_times} frozen={b1.locker.frozen} alive={b1.isactive}")
        eng.terminate()
    run("P2: 1v1 单锁节奏 (5次)", one, trials=5)

# P3: 命中后攻击者释放可换目标
def p3():
    def one(t):
        random.seed(300 + t)
        eng = make_engine(wships=[('w1',(100000,300000))], bships=[('b1',(130000,300000)),('b2',(130000,318000))])
        eng.activate(); eng.update(delta=12)
        b1, b2, w1 = eng.unit_by_name('b1'), eng.unit_by_name('b2'), eng.unit_by_name('w1')
        eng.cmd_lock('w1','b1')
        eng.update(delta=310)
        print(f"  [seed{t}] +310s: b1 hits={b1.locker.locked_times} w1.locking={w1.locker.locking}")
        ok = eng.cmd_lock('w1','b2')
        print(f"    尝试换锁b2 = {ok}  w1.locking_name={w1.locker.locking_name}")
        eng.terminate()
    run("P3: 命中后攻击者释放可换目标 (5次)", one, trials=5)

# P4: 冻结目标可被追刀 → 冻结期+300s击杀
def p4():
    def one(t):
        random.seed(400 + t)
        eng = make_engine(wships=[('w1',(100000,300000)),('w2',(100000,283000))], bships=[('b1',(130000,300000))])
        eng.activate(); eng.update(delta=12)
        b1 = eng.unit_by_name('b1')
        eng.cmd_lock('w1','b1'); eng.cmd_lock('w2','b1')
        eng.update(delta=310)
        if b1.locker.locked_times < 1:
            print(f"  [seed{t}] 首轮0hit, 跳过"); eng.terminate(); return
        print(f"  [seed{t}] t0+310: hits={b1.locker.locked_times} frozen={b1.locker.frozen}")
        ok = eng.cmd_lock('w2','b1')   # 冻结中再锁
        eng.update(delta=305)
        print(f"    冻结中w2再锁={ok}  +305s: hits={b1.locker.locked_times} frozen={b1.locker.frozen} alive={b1.isactive}")
        eng.terminate()
    run("P4: 冻结目标追刀 (5次)", one, trials=5)

# P5: UAV目指 → USV锁 自身雷达(35km)外目标(39km)
def p5():
    def one(t):
        random.seed(500 + t)
        eng = make_engine(wships=[('w1',(100000,300000))], bships=[('b1',(139000,300000))],
                          wuavs=[('wuav1',(134000,300000))])
        eng.activate(); eng.update(delta=12)
        w1, b1 = eng.unit_by_name('w1'), eng.unit_by_name('b1')
        white_sees = 'b1' in eng.get_white_targets()[1]
        print(f"  [seed{t}] dist(w1,b1)={dist(w1,b1):.0f}m(>35km) 白方全体观测含b1={white_sees}")
        ok = eng.cmd_lock('w1','b1')
        print(f"    w1锁b1 = {ok}  (UAV目指 → USV锁40km内目标?)")
        if ok:
            eng.update(delta=310)
            print(f"    +310s: b1 hits={b1.locker.locked_times} frozen={b1.locker.frozen}")
        eng.terminate()
    run("P5: UAV目指支持USV超雷达锁定 (3次)", one, trials=3)

# P6: 被锁后撤离40km是否解锁 (黑UAV目指锁白, 白东逃)
def p6():
    def one(t):
        random.seed(600 + t)
        eng = make_engine(wships=[('w1',(140000,300000))], bships=[('b1',(105000,300000))],
                          buavs=[('buav1',(139000,300000))])
        eng.activate(); eng.update(delta=12)
        w1, b1 = eng.unit_by_name('w1'), eng.unit_by_name('b1')
        eng.black_cmd_lock('b1','w1')
        d0 = dist(w1,b1)
        print(f"  [seed{t}] 黑锁白: dist={d0:.0f} w1被锁={w1.locker.locked}")
        w1.motor.set_target_angle(90); w1.motor.set_target_speed(20)  # 向东逃(黑在西)
        eng.update(delta=150)
        print(f"    +150s dist={dist(w1,b1):.0f} w1被锁={w1.locker.locked}")
        eng.update(delta=150)
        print(f"    +300s dist={dist(w1,b1):.0f} w1被锁={w1.locker.locked} w1被命中={w1.locker.locked_times} frozen={w1.locker.frozen}")
        eng.terminate()
    run("P6: 被锁后撤离40km解锁 (1次)", one, trials=1)

# P7: 突防判定
def p7():
    def one(t):
        eng = make_engine(wships=[('w1',(100000,300000))], bships=[('b1',(49000,300000))])
        eng.activate(); eng.update(delta=3)
        b1 = eng.unit_by_name('b1')
        print(f"  [seed{t}] b1 x=49000(静止): black_success={len(eng.judge.black_success)} b1.alive={b1.isactive}")
        st = eng.get_state()
        print(f"    ended={st['ended']} reason={st['ended_reason']}")
        eng.terminate()
    def two(t):
        random.seed(710 + t)
        eng = make_engine(wships=[('w1',(100000,300000)),('w2',(100000,283000))], bships=[('b1',(51500,300000))])
        eng.activate(); eng.update(delta=12)
        b1 = eng.unit_by_name('b1')
        eng.cmd_lock('w1','b1'); eng.cmd_lock('w2','b1')
        eng.update(delta=310)
        print(f"  [seed{t}] b1 x=51500 hits={b1.locker.locked_times} frozen={b1.locker.frozen}")
        eng.update(delta=200)
        print(f"    +200s: black_success={len(eng.judge.black_success)} b1.alive={b1.isactive} (frozen静止在51500, 不突防)")
        eng.terminate()
    run("P7a: 突防线几何判定", one, trials=1)
    run("P7b: frozen黑船静止于51500不误判", two, trials=2)

# P8: 运动学
def p8():
    def one(t):
        eng = make_engine(wships=[('w1',(0,300000))], bships=[('b1',(100000,300000))])
        eng.activate(); eng.update(delta=12)
        w1 = eng.unit_by_name('w1')
        print(f"  [seed{t}] 初始 speed={w1.motor.real_speed:.1f} course={np.rad2deg(w1.motor.real_angle):.1f}")
        w1.motor.set_target_speed(20); w1.motor.set_target_angle(90)
        eng.update(delta=30)
        print(f"    指令20/90后+30s: speed={w1.motor.real_speed:.1f} course={np.rad2deg(w1.motor.real_angle):.1f} x={w1.coords[0]:.0f}")
        w1.motor.set_target_angle(180)
        eng.update(delta=20)
        c = np.rad2deg(w1.motor.real_angle)
        print(f"    转向180后+20s: course={c:.1f} (期望≈90+5*20=190→180)")
        eng.terminate()
    run("P8: USV运动学", one, trials=1)

# P9: UAV ±30°扇区
def p9():
    def one(t):
        eng = make_engine(wships=[('w1',(0,300000))], bships=[('b_in',(50000,315000)),('b_out',(40000,340000))],
                          wuavs=[('wuav1',(0,300000))])
        eng.activate(); eng.update(delta=12)
        wuav = eng.unit_by_name('wuav1')
        wuav.motor.set_target_angle(90)  # 朝东, 扇区[60,120]
        eng.update(delta=5)
        in_seen = 'b_in' in eng.get_white_targets()[1]
        out_seen = 'b_out' in eng.get_white_targets()[1]
        print(f"  [seed{t}] UAV朝东90°扇区[60,120]: 方位73.3°(b_in)可见={in_seen}  方位45°(b_out)可见={out_seen}")
        eng.terminate()
    run("P9: UAV ±30°前向扇区", one, trials=1)

# P10: 黑UAV目指 → 黑USV锁白
def p10():
    def one(t):
        random.seed(800 + t)
        eng = make_engine(wships=[('w1',(140000,300000))], bships=[('b1',(105000,300000))],
                          buavs=[('buav1',(139000,300000))])
        eng.activate(); eng.update(delta=12)
        buav = eng.unit_by_name('buav1')
        buav.motor.set_target_angle(270)  # 朝西
        eng.update(delta=5)
        w1, b1 = eng.unit_by_name('w1'), eng.unit_by_name('b1')
        black_sees = 'w1' in eng.get_black_targets()
        print(f"  [seed{t}] 黑方观测含w1={black_sees} 距离={dist(w1,b1):.0f}m")
        ok = eng.black_cmd_lock('b1','w1')
        print(f"    黑b1锁白w1 = {ok}")
        eng.terminate()
    run("P10: 黑UAV目指支持黑USV锁 (2次)", one, trials=2)

if __name__ == '__main__':
    p1(); p2(); p3(); p4(); p5(); p6(); p7(); p8(); p9(); p10()
    print("\nALL PROBES DONE")
