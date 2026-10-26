# -*- coding: utf-8 -*-
import sys
sys.path.insert(0,"/root/autodl-tmp/hsystem")
from agent_hybrid_max_range import MaxRangeController, MaxRangeAgentMain, BAND_MID, BAND_INNER, BAND_OUTER
from agent_hybrid_press_search import PressSearchController
from agent_hybrid_v5 import LOCK_RANGE

def test_band_within_lock_range():
    assert BAND_OUTER<=LOCK_RANGE
    assert BAND_INNER<BAND_MID<BAND_OUTER
def test_subclass(): assert issubclass(MaxRangeController, PressSearchController)
def test_agent(): assert isinstance(MaxRangeAgentMain(use_uavs=True).usv_ctrl, MaxRangeController)
def test_standoff_uses_max_band():
    c=MaxRangeController()
    # target 100km east, pos origin -> should move toward it (course 90)
    a=c._standoff_move("u",(0.0,0.0),(100000.0,0.0),34000.0,29500.0,36500.0)
    assert "target_course=90.0" in a[0], a
def _all():
    fns=[v for k,v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    p=0
    for f in fns:
        try: f(); p+=1
        except Exception as e: print("FAIL",f.__name__,repr(e))
    print(f"passed={p}/{len(fns)}"); return p==len(fns)
if __name__=="__main__": sys.exit(0 if _all() else 1)
