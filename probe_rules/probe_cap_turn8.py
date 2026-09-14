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

# A: 不干预, 初始 10 m/s 朝东, 大跨度 update
eng = setup(); w = eng.unit_by_name('w1'); m = w.motor
eng.update(delta=300)
print(f"A 巡航300s: x={w.coords[0]:.0f} (初始100000, 期望+3000) speed={m.real_speed:.1f} course={m.course}")
eng.terminate()

# B: 转180°后用大跨度 update(120) 检查是否持续向西
eng = setup(); w = eng.unit_by_name('w1'); m = w.motor
m.set_target_speed(20); m.set_target_angle(180)
eng.update(delta=30)
x1 = w.coords[0]; print(f"B 转180后+30s: x={x1:.0f} speed={m.real_speed:.1f} course={m.course}")
eng.update(delta=120)
print(f"B 再+120s: x={w.coords[0]:.0f} (Δ={w.coords[0]-x1:.0f}, 20m/s*120s=-2400期望) speed={m.real_speed:.1f} course={m.course}")
eng.terminate()

# C: 转90°后大跨度
eng = setup(); w = eng.unit_by_name('w1'); m = w.motor
m.set_target_speed(20); m.set_target_angle(0)   # 正北
eng.update(delta=30)
y1 = w.coords[1]; print(f"C 转0后+30s: y={y1:.0f} speed={m.real_speed:.1f} course={m.course}")
eng.update(delta=120)
print(f"C 再+120s: y={w.coords[1]:.0f} (Δ={w.coords[1]-y1:.0f}, 20m/s*120s=+2400期望)")
eng.terminate()
print("TURN8 DONE")
