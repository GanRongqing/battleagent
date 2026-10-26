# -*- coding: utf-8 -*-
import sys
sys.path.insert(0,"/root/autodl-tmp/hsystem")
from agent_hybrid_fleet_recon import FleetTetheredUAVManager, FleetReconAgentMain, FRONT_OFFSET
from agent_hybrid_v5 import UAVManager
class O:
    def __init__(s,usvs,uavs): s.usvs=usvs; s.uavs=uavs; s.now=0.0; s.passive=[]
class L:
    def can_fly(s,*a): return True
class Tr:
    tracks={}
def test_tether_ahead_and_spread():
    m=FleetTetheredUAVManager(enabled=True)
    usvs=[{"name":"s1","is_alive":True,"position":(200000,0)},{"name":"s2","is_alive":True,"position":(240000,0)}]
    pts=m._tether_points(usvs,3)
    assert all(abs(p[0]-(240000+FRONT_OFFSET))<1e-6 for p in pts)
    assert len({round(p[1],1) for p in pts})==3
def test_subclass(): assert issubclass(FleetTetheredUAVManager, UAVManager)
def test_agent_uses_manager():
    m=FleetReconAgentMain(use_uavs=True)
    assert isinstance(m.uav_mgr, FleetTetheredUAVManager)
def _all():
    fns=[v for k,v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    p=0
    for f in fns:
        try: f(); p+=1
        except Exception as e: print("FAIL",f.__name__,repr(e))
    print(f"passed={p}/{len(fns)}"); return p==len(fns)
if __name__=="__main__": sys.exit(0 if _all() else 1)
