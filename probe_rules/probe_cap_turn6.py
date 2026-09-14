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

# 追踪 _move 调用期间 real_angle 的取值序列
orig = m._move
calls = []
def traced():
    before = np.rad2deg(m.real_angle)
    orig()
    calls.append(before)
m._move = traced

m.set_target_speed(10); m.set_target_angle(180)
for i in range(10):
    engine.update(delta=0.1)
    print(f"  +{i+1}0ms: real_angle={np.rad2deg(m.real_angle):.1f}° x={w1.coords[0]:.0f} target={m.target_angle}")
print(f"_move被调用 {len(calls)} 次, 每次调用前 real_angle: {[round(c,1) for c in calls[:20]]}")
engine.terminate()
print("TURN6 DONE")
