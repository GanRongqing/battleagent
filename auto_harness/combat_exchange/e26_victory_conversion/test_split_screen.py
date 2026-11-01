# -*- coding: utf-8 -*-
import sys
sys.path.insert(0,"/root/autodl-tmp/hsystem")
from agent_hybrid_split_screen import SplitScreenController, SplitScreenAgentMain, SCREEN_EVERY
from universal_safety import BoundaryAwareSafety, _predict, _inside
class L:
    def can_move(s,*a): return True
    def can_lock(s,*a): return True
    def can_fly(s,*a): return True
    def can_launch(s,*a): return True
    def can_land(s,*a): return True
class O:
    def __init__(s,usvs,uavs=()): s.usvs=usvs; s.uavs=list(uavs); s.passive=[]; s.now=0.0
def test_role_by_index():
    assert SplitScreenController._is_screen_unit("white_usv3")
    assert SplitScreenController._is_screen_unit("white_usv6")
    assert not SplitScreenController._is_screen_unit("white_usv1")
def test_agent_subclass():
    m=SplitScreenAgentMain(use_uavs=True)
    assert isinstance(m.usv_ctrl,SplitScreenController) and isinstance(m.safety,BoundaryAwareSafety)
def test_uav_safety_rewrites_outbound():
    s=BoundaryAwareSafety()
    obs=O([],[{"name":"white_uav1","is_alive":True,"position":(368000.0,0.0)}])
    out=s.filter([("white_uav1 飞行 target_speed=100.0 target_course=90.0","fly")],obs,L())
    assert "target_course" in out[0]["action_text"] and s.area_rewrites==1
def test_uav_inbound_untouched():
    s=BoundaryAwareSafety()
    obs=O([],[{"name":"white_uav1","is_alive":True,"position":(200000.0,0.0)}])
    out=s.filter([("white_uav1 飞行 target_speed=100.0 target_course=90.0","fly")],obs,L())
    assert s.area_rewrites==0
def _all():
    fns=[v for k,v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    p=0
    for f in fns:
        try: f(); p+=1
        except Exception as e: print("FAIL",f.__name__,repr(e))
    print(f"passed={p}/{len(fns)}"); return p==len(fns)
if __name__=="__main__": sys.exit(0 if _all() else 1)
