import os, sys, numpy as np
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
m = w1.motor
print(f"type(motor)={type(m).__name__}  _state_period={m._state_period}  attr.period={m.attr.period}")
print(f"max_angle_velocity(实例)={m.max_angle_velocity}  attr.max_angle_velocity={m.attr.max_angle_velocity}")
print(f"max_speed(实例)={m.max_speed}  max_acce(实例)={m.max_acce}")
# 小幅转向 90 -> 120 (30°), 每 0.05s 采样
m.set_target_speed(10); m.set_target_angle(120)
for i in range(4):
    engine.update(delta=0.05)
    cd = ((m.target_angle-m.real_angle)%(2*np.pi)) if m.target_angle is not None else None
    print(f"  +{i*0.05+0.05:.2f}s: real_angle={np.rad2deg(m.real_angle):.3f}° target_angle={m.target_angle} cw_diff={cd}")
engine.terminate()
print("TURN3 DONE")
