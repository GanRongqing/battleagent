# -*- coding: utf-8 -*-
import sys
sys.path.insert(0,"/root/autodl-tmp/hsystem")
from agent_hybrid_retreat_loss import StopPressAfterLossController, StopPressAfterLossAgentMain
from agent_hybrid_press_search import ADVANCE_STEP
from agent_hybrid_v5 import SCREEN_X

def test_default_presses():
    c=StopPressAfterLossController()
    assert c._lost is False
    assert c._screen_redirect((SCREEN_X,0),(SCREEN_X,0))==(SCREEN_X+ADVANCE_STEP,0)

def test_after_loss_screens():
    c=StopPressAfterLossController(); c._lost=True
    assert c._screen_redirect((SCREEN_X,0),(SCREEN_X,0))==(SCREEN_X,0)

def test_agent_controller():
    m=StopPressAfterLossAgentMain(use_uavs=True)
    assert isinstance(m.usv_ctrl, StopPressAfterLossController)

def _all():
    fns=[v for k,v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    p=0
    for f in fns:
        try: f(); p+=1
        except Exception as e: print("FAIL",f.__name__,repr(e))
    print(f"passed={p}/{len(fns)}"); return p==len(fns)
if __name__=="__main__": sys.exit(0 if _all() else 1)
