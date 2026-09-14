import sys; sys.path.insert(0,'/root/autodl-tmp/hsystem/hsystem/simserver'); sys.path.insert(0,'/root/autodl-tmp/hsystem/hsystem'); sys.path.insert(0,'/root/autodl-tmp/hsystem/hsystem/simulation')
import random, numpy as np
import simulation.core as core
random.seed(1)
engine = core.tzb_engine.TzbEngine('probe', flag=core.log.INFO, terminal=False, logtag='probe', cache=False)
engine.set_ratio(1000); engine.set_end_time(3600)
big = [(-100000,-200000),(500000,-200000),(500000,900000),(-100000,900000)]
engine.db["RadarWithGuider"]["distance"]=60000; engine.db["RadarWithGuider"]["sector"]=[-30,30]
engine.db["RadarWithGuider"]["detected_method"]="fixed"
engine.db["PlaneMotorTZB"]["max_speed"]=150
engine.db["AEW"]["motor"]="PlaneMotorTZB"; engine.db["AEW"]["radars"]=["RadarWithGuider"]
engine.gen_platform('wuav1','AEW','RED',[100000,300000],150,90,100,coordinate_system="Cartesian")
u = engine.unit_by_name('wuav1')
intel = u.intelligence
print('intel class:', type(intel).__name__)
print('intel.model:', getattr(intel,'model',None))
print('intel.db:', dict(intel.db))
print('intel.attr radar_update_time:', intel.attr['radar_update_time'])
print('eng.db Intelligence radar_update_time:', engine.db['Intelligence']['radar_update_time'])
print('intel._work_prune_attr:', getattr(intel,'attr',{}))
