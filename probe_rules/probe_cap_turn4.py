import os, sys, numpy as np
_BASE = '/root/autodl-tmp/hsystem/hsystem'
sys.path.insert(0, _BASE + '/simserver'); sys.path.insert(0, _BASE); sys.path.insert(0, _BASE + '/simulation')
import simulation.core as core

def setup(speed, course):
    engine = core.tzb_engine.TzbEngine('probe', flag=core.log.INFO, terminal=False, logtag='probe', cache=False)
    engine.set_ratio(1000); engine.set_end_time(3600)
    big = [(-100000, -200000), (500000, -200000), (500000, 900000), (-100000, 900000)]
    engine.db["Ship"]["motor"] = "ShipMotorTZB"; engine.db["Ship"]["radars"] = ["RadarWithGuider"]
    engine.gen_platform('w1', 'Ship', 'RED', [100000, 300000], speed, course, coordinate_system="Cartesian")
    all_units = [engine.unit_by_name('w1')]
    judge = engine.gen_judge_system("JudgeSystemTZB", all_units)
    judge.set_area(big + [big[0]])
    def start(e): judge.activate()
    engine.set_starter(start)
    engine.activate(); engine.update(delta=5)
    return engine

for target in (100, 120, 180, 270):
    eng = setup(10, 90); w = eng.unit_by_name('w1'); m = w.motor
    m.set_target_speed(10); m.set_target_angle(target)
    traj = []
    for i in range(60):
        eng.update(delta=0.02)
        ta = np.rad2deg(m.real_angle) if m.target_angle is None else None
        traj.append(round(np.rad2deg(m.real_angle), 1))
        if m.target_angle is None:
            break
    print(f"90°->{target}°: 完成用时 {len(traj)*0.02:.2f}s, 轨迹(每0.02s): {traj}")
    eng.terminate()
print("TURN4 DONE")
