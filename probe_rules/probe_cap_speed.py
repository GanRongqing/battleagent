"""探针: 直接测量 ShipMotorTZB / PlaneMotorTZB 真实可达速度 + 转向/加速常数
用与官方脚本一致的 db 配置(不覆盖 ShipMotorTZB.max_speed)
"""
import os, sys, random
_BASE = '/root/autodl-tmp/hsystem/hsystem'
sys.path.insert(0, _BASE + '/simserver'); sys.path.insert(0, _BASE); sys.path.insert(0, _BASE + '/simulation')
import numpy as np
import simulation.core as core

def make_engine(ratio=1000):
    engine = core.tzb_engine.TzbEngine('probe', flag=core.log.INFO, terminal=False, logtag='probe', cache=False)
    engine.set_ratio(ratio); engine.set_end_time(3600)
    big = [(-100000, -200000), (500000, -200000), (500000, 900000), (-100000, 900000)]
    engine.db["RadarWithGuider"]["distance"] = 35_000
    engine.db["RadarWithGuider"]["sector"] = [0, 360]
    engine.db["RadarWithGuider"]["detected_method"] = "fixed"
    engine.db["Ship"]["motor"] = "ShipMotorTZB"; engine.db["Ship"]["radars"] = ["RadarWithGuider"]
    engine.gen_platform('w1', 'Ship', 'RED', [100000, 300000], 10, 90, coordinate_system="Cartesian")
    engine.db["PlaneMotorTZB"]["max_speed"] = 150
    engine.db["AEW"]["motor"] = "PlaneMotorTZB"; engine.db["AEW"]["radars"] = ["RadarWithGuider"]
    engine.gen_platform('wuav1', 'AEW', 'RED', [100000, 300000], 150, 90, 100, coordinate_system="Cartesian")
    all_units = [engine.unit_by_name(n) for n in ('w1','wuav1')]
    judge = engine.gen_judge_system("JudgeSystemTZB", all_units)
    judge.set_area(big + [big[0]])
    def start(engine):
        engine.turn_on_radars(); engine.turn_on_lockers()
        engine.unit_by_name('wuav1').uavbattery.turn_on()
        judge.activate()
    engine.set_starter(start)
    return engine

eng = make_engine(); eng.activate(); eng.update(delta=5)
w1 = eng.unit_by_name('w1'); u1 = eng.unit_by_name('wuav1')
print(f"motor db max_speed: ship attr={w1.motor.attr.max_speed}  plane attr={u1.motor.attr.max_speed}")
print(f"初始: w1 speed={w1.motor.real_speed:.1f} course={w1.motor.course:.1f} | wuav speed={u1.motor.real_speed:.1f}")
# 给船下令 30 m/s 朝东, 无人机 200 m/s 朝东
w1.motor.set_target_speed(30); w1.motor.set_target_angle(90)
u1.motor.set_target_speed(200); u1.motor.set_target_angle(90)
for dt in (5, 10, 20, 30, 60):
    eng.update(delta=dt)
    print(f"  +{dt:3d}s: w1 speed={w1.motor.real_speed:.2f} course={w1.motor.course:.1f} | wuav speed={u1.motor.real_speed:.2f}")
eng.terminate()
# 转向速率: 船 0->180
eng = make_engine(); eng.activate(); eng.update(delta=5)
w1 = eng.unit_by_name('w1')
w1.motor.set_target_speed(10); w1.motor.set_target_angle(180)
t0 = eng.time
while w1.motor.course < 179 and eng.time - t0 < 60:
    eng.update(delta=1)
dt = eng.time - t0
print(f"船 90°->180° 用 {dt:.0f}s (速率 {90/dt:.2f}°/s)")
eng.terminate()
print("SPEED PROBE DONE")
