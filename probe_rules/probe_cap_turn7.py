import os, sys, numpy as np
_BASE = '/root/autodl-tmp/hsystem/hsystem'
sys.path.insert(0, _BASE + '/simserver'); sys.path.insert(0, _BASE); sys.path.insert(0, _BASE + '/simulation')
import simulation.core as core

def setup():
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
    return engine

eng = setup(); w = eng.unit_by_name('w1'); m = w.motor
print(f"初始: course={m.course} x={w.coords[0]:.0f} t={eng.time}")
# 转弯 90->180, 然后用 update(1) 检查是否持续移动
m.set_target_speed(20); m.set_target_angle(180)
for i in range(5):
    eng.update(delta=1)
    print(f"  +{i+1}s: real_angle={np.rad2deg(m.real_angle):.1f}° x={w.coords[0]:.0f} (Δx={w.coords[0]-100000:.0f}) course={m.course}")
eng.terminate()
# 对照: 不转弯直接走
eng = setup(); w = eng.unit_by_name('w1'); m = w.motor
m.set_target_speed(20); m.set_target_angle(90)
for i in range(5):
    eng.update(delta=1)
    print(f"  straight +{i+1}s: x={w.coords[0]:.0f} (Δx={w.coords[0]-100000:.0f})")
eng.terminate()
print("TURN7 DONE")
