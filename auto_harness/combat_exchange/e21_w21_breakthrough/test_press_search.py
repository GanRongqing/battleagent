# -*- coding: utf-8 -*-
import sys
sys.path.insert(0,"/root/autodl-tmp/hsystem")
from agent_hybrid_press_search import PressSearchController, PressSearchAgentMain, ADVANCE_STEP
from agent_hybrid_budget_gate import BudgetGateController
from agent_hybrid_v5 import SCREEN_X

def test_screen_redirect_east():
    c=PressSearchController()
    assert c._screen_redirect((SCREEN_X,0),(SCREEN_X,0))==(SCREEN_X+ADVANCE_STEP,0)
    assert c._screen_redirect((200000,50000),(SCREEN_X,50000))==(200000+ADVANCE_STEP,50000)

def test_nonscreen_unchanged():
    c=PressSearchController()
    assert c._screen_redirect((100000,0),(250000,0))==(250000,0)
    assert c._screen_redirect((100000,0),None) is None

def test_move_never_degenerate_at_screen():
    c=PressSearchController()
    act=c._move("u",(SCREEN_X,0),(SCREEN_X,0))
    assert "target_course=90.0" in act[0], act

def test_is_budget_gate_subclass():
    assert issubclass(PressSearchController, BudgetGateController)

def test_agent_uses_controller():
    m=PressSearchAgentMain(use_uavs=True)
    assert isinstance(m.usv_ctrl, PressSearchController)

def _all():
    fns=[v for k,v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    p=0
    for f in fns:
        try: f(); p+=1
        except Exception as e: print("FAIL",f.__name__,repr(e))
    print(f"passed={p}/{len(fns)}"); return p==len(fns)
if __name__=="__main__": sys.exit(0 if _all() else 1)
