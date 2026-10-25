# -*- coding: utf-8 -*-
import sys
sys.path.insert(0,"/root/autodl-tmp/hsystem")
from agent_hybrid_bearing_home import PassiveHomeController, PassiveHomeAgentMain
from agent_hybrid_budget_gate import BudgetGateController
class O:
    def __init__(s,usvs,passive): s.usvs=usvs; s.passive=passive; s.now=0.0
def test_bearing_override():
    c=PassiveHomeController()
    c.targets={}
    c.state={}
    obs=O([{"name":"usv1","is_alive":True,"position":(100000,0)}],
          [{"name":"usv9","bearing":135.0,"detected_by":"usv1"}])
    acts=c.step(obs,{}, {}, {},[])
    a=[x for x in acts if x[0].startswith("usv1")][0]
    assert "target_course=135.0" in a[0], a
def test_no_bearing_untouched():
    c=PassiveHomeController(); c.targets={}; c.state={}
    obs=O([{"name":"usv1","is_alive":True,"position":(100000,0)}],[])
    acts=c.step(obs,{}, {}, {},[])
    a=[x for x in acts if x[0].startswith("usv1")][0]
    assert "target_course=135.0" not in a[0]
def test_subclass_and_agent():
    assert issubclass(PassiveHomeController,BudgetGateController)
    assert isinstance(PassiveHomeAgentMain(use_uavs=True).usv_ctrl, PassiveHomeController)
def _all():
    fns=[v for k,v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    p=0
    for f in fns:
        try: f(); p+=1
        except Exception as e: print("FAIL",f.__name__,repr(e))
    print(f"passed={p}/{len(fns)}"); return p==len(fns)
if __name__=="__main__": sys.exit(0 if _all() else 1)
