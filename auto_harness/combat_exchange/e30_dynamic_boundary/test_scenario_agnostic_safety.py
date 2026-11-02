# -*- coding: utf-8 -*-
import sys
sys.path.insert(0,"/root/autodl-tmp/hsystem")
from scenario_agnostic_safety import ScenarioAgnosticBoundarySafety
from agent_hybrid_v5 import ActionSafety
W2=[[0,-277800],[370400,-277800],[370400,277800],[0,277800],[0,-277800]]
SC=[[50000,673205],[250000,673205],[300000,586602],[300000,86602],[250000,0],[50000,0],[0,86602],[0,586602],[50000,673205]]
class O:
    def __init__(s,usvs,uavs=(),area=None): s.usvs=usvs; s.uavs=list(uavs); s.public_area=area
class L:
    def can_move(s,*a): return True
    def can_lock(s,*a): return True
    def can_fly(s,*a): return True
    def can_launch(s,*a): return True
    def can_land(s,*a): return True
def test_subclass(): assert issubclass(ScenarioAgnosticBoundarySafety,ActionSafety)
def test_scale_interior_not_rewritten():
    s=ScenarioAgnosticBoundarySafety()
    obs=O([{"name":"white_usv1","is_alive":True,"position":(600.0,405000.0)}],area=SC)
    s.filter([("white_usv1 移动 target_speed=20.0 target_course=90.0","move")],obs,L())
    assert s.available and s.area_rewrites==0
def test_w2_interior_not_rewritten():
    s=ScenarioAgnosticBoundarySafety()
    obs=O([{"name":"white_usv1","is_alive":True,"position":(150000.0,0.0)}],area=W2)
    s.filter([("white_usv1 移动 target_speed=20.0 target_course=90.0","move")],obs,L())
    assert s.available and s.area_rewrites==0
def test_predicted_out_rewritten():
    s=ScenarioAgnosticBoundarySafety()
    obs=O([{"name":"white_usv1","is_alive":True,"position":(299900.0,300000.0)}],area=SC)  # near x=300k edge
    out=s.filter([("white_usv1 移动 target_speed=20.0 target_course=90.0","move")],obs,L())
    assert s.area_rewrites==1 and s.predicted_out_rewrites==1
def test_uav_out_rewritten():
    s=ScenarioAgnosticBoundarySafety()
    obs=O([],[{"name":"white_uav1","is_alive":True,"position":(299000.0,300000.0)}],area=SC)
    s.filter([("white_uav1 飞行 target_speed=100.0 target_course=90.0","fly")],obs,L())
    assert s.area_rewrites==1
def test_missing_area_no_rewrite_and_unavailable():
    s=ScenarioAgnosticBoundarySafety()
    obs=O([{"name":"white_usv1","is_alive":True,"position":(600.0,405000.0)}],area=None)
    out=s.filter([("white_usv1 移动 target_speed=20.0 target_course=90.0","move")],obs,L())
    assert (not s.available) and s.area_rewrites==0 and "target_course=90.0" in out[0]["action_text"]
def test_invalid_polygon():
    s=ScenarioAgnosticBoundarySafety()
    obs=O([{"name":"u","is_alive":True,"position":(0,0)}],area=[[0,0],[0,0],[0,0]])
    s.filter([("u 移动 target_speed=20.0 target_course=90.0","move")],obs,L())
    assert not s.available
def test_lock_untouched():
    s=ScenarioAgnosticBoundarySafety()
    obs=O([{"name":"white_usv1","is_alive":True,"position":(299000.0,300000.0)}],area=SC)
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
