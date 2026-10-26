# -*- coding: utf-8 -*-
import sys
sys.path.insert(0,"/root/autodl-tmp/hsystem")
import agent_hybrid_budget_gate as bg
from agent_hybrid_unlimited_pkg import UnlimitedPkgAgentMain, UnlimitedPkgController
from agent_hybrid_press_search import PressSearchController
def test_budget_unlimited():
    assert bg.MAX_TOTAL_PACKAGES >= 10**6
def test_subclass(): assert issubclass(UnlimitedPkgController, PressSearchController)
def test_agent(): assert isinstance(UnlimitedPkgAgentMain(use_uavs=True).usv_ctrl, UnlimitedPkgController)
def _all():
    fns=[v for k,v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    p=0
    for f in fns:
        try: f(); p+=1
        except Exception as e: print("FAIL",f.__name__,repr(e))
    print(f"passed={p}/{len(fns)}"); return p==len(fns)
if __name__=="__main__": sys.exit(0 if _all() else 1)
