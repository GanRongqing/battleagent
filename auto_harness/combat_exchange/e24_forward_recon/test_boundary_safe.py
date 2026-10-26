# -*- coding: utf-8 -*-
import sys
sys.path.insert(0,"/root/autodl-tmp/hsystem")
from agent_hybrid_boundary_safe import BoundarySafeController, BoundarySafeAgentMain, SAFE_X, SAFE_Y
from agent_hybrid_press_search import PressSearchController
from agent_hybrid_fleet_recon import FleetTetheredUAVManager
def test_clamp_far_east():
    c=BoundarySafeController()
    assert c._clamp((300000.0,0.0),(400000.0,0.0))==(SAFE_X,0.0)
def test_fallback_west_at_edge():
    c=BoundarySafeController()
    tx,ty=c._clamp((356000.0,0.0),(456000.0,0.0)); assert tx<356000.0
def test_clamp_y():
    c=BoundarySafeController()
    assert c._clamp((0.0,0.0),(100000.0,999999.0))[1]==SAFE_Y
def test_agent_recon_and_boundary():
    m=BoundarySafeAgentMain(use_uavs=True)
    assert isinstance(m.usv_ctrl,BoundarySafeController) and isinstance(m.uav_mgr,FleetTetheredUAVManager)
def _all():
    fns=[v for k,v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    p=0
    for f in fns:
        try: f(); p+=1
        except Exception as e: print("FAIL",f.__name__,repr(e))
    print(f"passed={p}/{len(fns)}"); return p==len(fns)
if __name__=="__main__": sys.exit(0 if _all() else 1)
