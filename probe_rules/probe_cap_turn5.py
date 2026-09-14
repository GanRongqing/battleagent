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
w1 = engine.unit_by_name('w1'); m = w1.motor
print(f"max_angle_velocity(实例, 被当作弧度用)={m.max_angle_velocity} rad/tick阈值={m.max_angle_velocity*m._state_period}")
print(f"初始: course={m.course} x={w1.coords[0]:.0f} t={engine.time}")
# 指令 20 m/s 朝90, 然后转向180, 每1s采样30次
m.set_target_speed(20); m.set_target_angle(90)
engine.update(delta=30)
print(f"  +30s: speed={m.real_speed:.1f} x={w1.coords[0]:.0f} (20m/s*30s位移={w1.coords[0]-100000:.0f}m 校验仿真时基)")
m.set_target_angle(180)
row = []
for i in range(40):
    engine.update(delta=1)
    row.append(f"{np.rad2deg(m.real_angle):6.1f}")
    if m.target_angle is None:
        done = i
print(f"  转向180后每1s course: {' '.join(row)}")
print(f"  完成用 {row.index(f'{180.0:6.1f}')+1 if f'{180.0:6.1f}' in row else '?'}s")
engine.terminate()
print("TURN5 DONE")
