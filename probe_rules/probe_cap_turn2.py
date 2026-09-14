import os, sys
_BASE = '/root/autodl-tmp/hsystem/hsystem'
sys.path.insert(0, _BASE + '/simserver'); sys.path.insert(0, _BASE); sys.path.insert(0, _BASE + '/simulation')
import numpy as np
import simulation.core as core

engine = core.tzb_engine.TzbEngine('probe', flag=core.log.INFO, terminal=False, logtag='probe', cache=False)
engine.set_ratio(1000); engine.set_end_time(3600)
big = [(-100000, -200000), (500000, -200000), (500000, 900000), (-100000, 900000)]
engine.db["Ship"]["motor"] = "ShipMotorTZB"; engine.db["Ship"]["radars"] = ["RadarWithGuider"]
engine.gen_platform('w1', 'Ship', 'RED', [100000, 300000], 10, 90, coordinate_system="Cartesian")
all_units = [engine.unit_by_name('w1')]
judge = engine.gen_judge_system("JudgeSystemTZB", all_units)
judge.set_area(big + [big[0]])
def start(e): judge.activate()
engine.set_starter(start)
engine.activate(); engine.update(delta=5)
w1 = engine.unit_by_name('w1')
print(f"max_angle_velocity attr = {w1.motor.attr.max_angle_velocity} (标注角度制)")
w1.motor.set_target_speed(10); w1.motor.set_target_angle(180)
for i in range(6):
    engine.update(delta=0.1)
    print(f"  +{i*0.1+0.1:.1f}s: real_angle={np.rad2deg(w1.motor.real_angle):.2f}° course={w1.motor.course:.2f} target_angle={w1.motor.target_angle}")
engine.terminate()

# 也测无人机转向 (max_angle_velocity=10)
engine = core.tzb_engine.TzbEngine('probe', flag=core.log.INFO, terminal=False, logtag='probe', cache=False)
engine.set_ratio(1000); engine.set_end_time(3600)
engine.db["PlaneMotorTZB"]["max_speed"] = 150
engine.db["AEW"]["motor"] = "PlaneMotorTZB"; engine.db["AEW"]["radars"] = ["RadarWithGuider"]
engine.gen_platform('wuav1', 'AEW', 'RED', [100000, 300000], 150, 90, 100, coordinate_system="Cartesian")
all_units = [engine.unit_by_name('wuav1')]
judge = engine.gen_judge_system("JudgeSystemTZB", all_units)
judge.set_area(big + [big[0]])
def start(e): judge.activate()
engine.set_starter(start)
engine.activate(); engine.update(delta=5)
u = engine.unit_by_name('wuav1')
print(f"UAV max_angle_velocity = {u.motor.attr.max_angle_velocity}")
u.motor.set_target_speed(150); u.motor.set_target_angle(0)
for i in range(6):
    engine.update(delta=0.1)
    print(f"  UAV +{i*0.1+0.1:.1f}s: real_angle={np.rad2deg(u.motor.real_angle):.2f}° course={u.motor.course:.2f}")
engine.terminate()
print("TURN2 DONE")
