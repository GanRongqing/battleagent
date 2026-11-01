# -*- coding: utf-8 -*-
import sys
sys.path.insert(0,"/root/autodl-tmp/hsystem")
from universal_safety import BoundaryAwareSafety, _inside, _predict, CENTER, MARGIN, AREA_XMAX
from agent_hybrid_v5 import ActionSafety, USV_SPEED
class O:
    def __init__(s,usvs,uavs=()): s.usvs=usvs; s.uavs=list(uavs)
class L:
    def can_move(s,*a): return True
    def can_lock(s,*a): return True
    def can_fly(s,*a): return True
    def can_launch(s,*a): return True
    def can_land(s,*a): return True
def test_subclass(): assert issubclass(BoundaryAwareSafety, ActionSafety)
def test_predict_east(): 
    x,y=_predict(0,0,20,90); assert x>0 and abs(y)<1e-6
def test_rewrites_outbound():
    s=BoundaryAwareSafety()
    obs=O([{"name":"white_usv1","is_alive":True,"position":(369000.0,0.0)}])
    out=s.filter([("white_usv1 移动 target_speed=20.0 target_course=90.0","move")],obs,L())
    assert "target_course" in out[0]["action_text"] and s.area_rewrites==1
def test_keeps_inside():
    s=BoundaryAwareSafety()
    obs=O([{"name":"white_usv1","is_alive":True,"position":(200000.0,0.0)}])
    out=s.filter([("white_usv1 移动 target_speed=20.0 target_course=90.0","move")],obs,L())
    assert s.area_rewrites==0
def test_lock_untouched():
    s=BoundaryAwareSafety()
    obs=O([{"name":"white_usv1","is_alive":True,"position":(369000.0,0.0)}])
    out=s.filter([("white_usv1 锁定 usv3","lock")],obs,L())
    assert out[0]["action_type"]=="lock"
def _all():
    fns=[v for k,v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    p=0
    for f in fns:
        try: f(); p+=1
        except Exception as e: print("FAIL",f.__name__,repr(e))
    print(f"passed={p}/{len(fns)}"); return p==len(fns)
if __name__=="__main__": sys.exit(0 if _all() else 1)
