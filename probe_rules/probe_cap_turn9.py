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

# 90° 转向 90->0 (北), speed 10; 每0.1s采样 real_angle 和 x (东向位移揭示转向耗时)
eng = setup(); w = eng.unit_by_name('w1'); m = w.motor
m.set_target_speed(10); m.set_target_angle(0)
x0 = w.coords[0]
print("t     real_angle   x(相对100051)")
for i in range(40):
    eng.update(delta=0.1)
    print(f"{eng.time:6.1f}  {np.rad2deg(m.real_angle):8.2f}   {w.coords[0]-x0:+.0f}")
    if m.target_angle is None and np.rad2deg(m.real_angle)==0:
        print(f"  → 转向完成于 {eng.time-5.0:.1f}s, 期间东移 {w.coords[0]-x0:.0f}m (10m/s → 耗时约{(w.coords[0]-x0)/10:.2f}s)")
        break
eng.terminate()
print("TURN9 DONE")
