# -*- coding: utf-8 -*-
import sys
sys.path.insert(0,"/root/autodl-tmp/hsystem")
from adaptive_skills import extract, Composer, SituationFeatures
from agent_hybrid_adaptive import AdaptiveController, AdaptiveUAVManager, AdaptiveAgentMain
from agent_hybrid_press_search import PressSearchController
from agent_hybrid_safe_recon import SafeReconAgentMain
from universal_safety import BoundaryAwareSafety
class T:
    def __init__(s,v): s.has_position=True; s.is_ship=True; s._v=v; s.name="b1"
    def is_visible(s,now): return s._v
class O:
    def __init__(s,usvs,uavs=(),passive=()): s.usvs=usvs; s.uavs=list(uavs); s.passive=list(passive); s.now=0.0
def test_features_counts():
    obs=O([{"name":"u1","is_alive":True,"position":(100000,0),"is_locking":True}],
          [{"name":"v1","is_alive":True,"position":(150000,0)}])
    f=extract(obs,{"b1":T(True)},0.0)
    assert f.active==1 and f.usv_alive==1 and f.usv_locking==1 and f.uav_forward==1 and f.has_threat
def test_no_threat_recon():
    c=Composer(); 
    for _ in range(3): usv,uav=c.decide(SituationFeatures(0,0,10,0,0,5,5,200000,0,False))
    assert usv=="ACTIVE_SEARCH" and uav=="FLEET_TETHERED_RECON"
def test_recovery_near_boundary():
    c=Composer()
    for _ in range(3): usv,uav=c.decide(SituationFeatures(0,0,10,0,0,5,5,10000,0,False))
    assert usv=="POSITION_RECOVERY"
def test_threat_broad_search():
    c=Composer(); usv,uav=c.decide(SituationFeatures(2,0,10,1,0,5,5,200000,0,True))
    assert uav=="BROAD_SEARCH"
def test_agent_wiring():
    m=AdaptiveAgentMain(use_uavs=True)
    assert isinstance(m.usv_ctrl,AdaptiveController) and isinstance(m.uav_mgr,AdaptiveUAVManager)
    assert isinstance(m.safety,BoundaryAwareSafety)
def test_controller_subclass(): assert issubclass(AdaptiveController,PressSearchController)
def _all():
    fns=[v for k,v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    p=0
    for f in fns:
        try: f(); p+=1
        except Exception as e: print("FAIL",f.__name__,repr(e))
    print(f"passed={p}/{len(fns)}"); return p==len(fns)
if __name__=="__main__": sys.exit(0 if _all() else 1)
