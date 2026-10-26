# -*- coding: utf-8 -*-
import sys, math
sys.path.insert(0,"/root/autodl-tmp/hsystem")
from agent_hybrid_standoff_hold import StandoffHoldController, StandoffHoldAgentMain, STANDOFF
from agent_hybrid_press_search import PressSearchController
from agent_hybrid_v5 import LOCK_BAND_OUTER

class T:
    is_ship=True; has_position=True
    def __init__(s,x,y): s.x=x; s.y=y
    def is_visible(s,now): return True
    def predicted_position(s,now): return (s.x,s.y)
class O:
    def __init__(s,usvs,now=0.0): s.usvs=usvs; s.passive=[]; s.now=now
class L:
    def can_lock(s,*a): return False
    def can_fly(s,*a): return True

def test_standoff_const():
    assert abs(STANDOFF-LOCK_BAND_OUTER)<1e-6
def test_is_press_subclass():
    assert issubclass(StandoffHoldController, PressSearchController)
def test_agent_controller():
    assert isinstance(StandoffHoldAgentMain(use_uavs=True).usv_ctrl, StandoffHoldController)
def test_targetless_moves_to_ring():
    c=StandoffHoldController(); c.targets={}; c.state={}
    obs=O([{"name":"u1","is_alive":True,"position":(100000.0,0.0)}])
    tracks={"b1":T(100000.0+100000.0,0.0)}   # contact 100km east
    acts=c.step(obs,tracks,L(), {},[])
    a=[x for x in acts if x[0].startswith("u1")][0]
    assert "target_course=90.0" in a[0], a   # move east toward ring
def test_far_inside_backs_off():
    c=StandoffHoldController(); c.targets={}; c.state={}
    obs=O([{"name":"u1","is_alive":True,"position":(110000.0,0.0)}])
    tracks={"b1":T(100000.0,0.0)}            # contact 10km west -> must back off east
    acts=c.step(obs,tracks,L(), {},[])
    a=[x for x in acts if x[0].startswith("u1")][0]
    assert "target_course=90.0" in a[0], a   # away (east) from contact
def _all():
    fns=[v for k,v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    p=0
    for f in fns:
        try: f(); p+=1
        except Exception as e: print("FAIL",f.__name__,repr(e))
    print(f"passed={p}/{len(fns)}"); return p==len(fns)
if __name__=="__main__": sys.exit(0 if _all() else 1)
