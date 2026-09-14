import os, sys
_BASE = '/root/autodl-tmp/hsystem/hsystem'
sys.path.insert(0, _BASE + '/simserver'); sys.path.insert(0, _BASE); sys.path.insert(0, _BASE + '/simulation')
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
print(f"attr max_speed={w1.motor.attr.max_speed} max_acce={w1.motor.attr.max_acce} max_angle_velocity={w1.motor.attr.max_angle_velocity} period={w1.motor.attr.period}")
print(f"初始 course={w1.motor.course:.2f} real_angle={w1.motor.real_angle:.4f}(rad) speed={w1.motor.real_speed:.2f}")
w1.motor.set_target_speed(10); w1.motor.set_target_angle(180)
t0 = engine.time
for i in range(20):
    engine.update(delta=1)
    print(f"  +{i+1:2d}s: course={w1.motor.course:.2f} real_angle={w1.motor.real_angle:.4f} target_angle={w1.motor.target_angle}")
    if w1.motor.target_angle is None: break
engine.terminate()
print("TURN PROBE DONE")
