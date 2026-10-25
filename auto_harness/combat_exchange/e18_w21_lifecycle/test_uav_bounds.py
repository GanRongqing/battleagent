# -*- coding: utf-8 -*-
import sys
sys.path.insert(0,"/root/autodl-tmp/hsystem")
import agent_hybrid_v5 as v5
from agent_hybrid_v5 import bearing_to, USV_SPEED
from agent_hybrid_uav_bounds import BoundedUAVManager, Y_MARGIN

_ORIG=v5.UAVManager.step
v5.UAVManager.step=lambda self,obs,tracker,legal,events,intent=None,threat_fn=None,coverage=None,mission=None: []

class O:
    def __init__(s,now,uavs,usvs=()): s.now=now; s.uavs=uavs; s.usvs=list(usvs)
class Tr: tracks={}

def _course(action):
    for tok in action[0].split():
        if tok.startswith("target_course="):
            return float(tok.split("=")[1])
    raise AssertionError(action)

def test_clamp_y():
    m=BoundedUAVManager(enabled=True); m._y_limit=200000.0
    act=m._fly("u1",(0,0),(100000,500000))
    want=bearing_to((0,0),(100000,200000))
    assert abs(_course(act)-want)<0.11, (_course(act),want)

def test_no_clamp_when_inside():
    m=BoundedUAVManager(enabled=True); m._y_limit=200000.0
    act=m._fly("u1",(0,0),(100000,150000))
    assert abs(_course(act)-bearing_to((0,0),(100000,150000)))<0.11

def test_limit_from_fleet():
    m=BoundedUAVManager(enabled=True); m._y_limit=None
    m.step(O(0.0,[{"name":"u1","is_alive":True,"position":(0,180000)}],
              [{"name":"s1","is_alive":True,"position":(0,100000)}]),Tr(),{},[])
    assert m._y_limit==180000+Y_MARGIN

def _all():
    fns=[v for k,v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    p=0
    for f in fns:
        try: f(); p+=1
        except Exception as e: print("FAIL",f.__name__,repr(e))
    v5.UAVManager.step=_ORIG
    print(f"passed={p}/{len(fns)}"); return p==len(fns)
if __name__=="__main__": sys.exit(0 if _all() else 1)
