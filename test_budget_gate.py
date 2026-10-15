import sys
import agent_hybrid_v5 as v5
from agent_hybrid_v5 import USV_SPEED
import agent_hybrid_budget_gate as C10
from agent_hybrid_budget_gate import BudgetGateController, MAX_TOTAL_PACKAGES

def _stub(self,obs,tracks,legal,alloc_result,events,intent=None,mission=None):
    return [(f"{u['name']} 移动 target_speed={USV_SPEED:.1f} target_course=90.0","move") for u in obs.usvs if u.get("is_alive")]
v5.USVController.step=_stub
class Track:
    def __init__(s,n,p,v=True,hp=True,ship=True): s.name=n;s._p=p;s._v=v;s.has_position=hp;s.is_ship=ship
    def is_visible(s,now): return s._v
    def predicted_position(s,now): return s._p
class Obs:
    def __init__(s,now,u): s.now=now;s.usvs=u
def usv(n,p,alive=True): return {"name":n,"is_alive":alive,"position":p,"is_locked":False,"locked_attacker":[],"is_locking":False}
def test_budget_cap():
    c=BudgetGateController()
    usvs=[usv("u1",(100000,0)),usv("u2",(101000,0)),usv("u3",(102000,0))]
    tracks={}
    c.targets={"u1":"t1","u2":None,"u3":None}; c.state={"u1":c.INTERCEPTING,"u2":c.INTERCEPTING,"u3":c.INTERCEPTING}
    # form MAX_TOTAL_PACKAGES packages across many targets
    for i in range(MAX_TOTAL_PACKAGES+2):
        tracks[f"t{i}"]=Track(f"t{i}",(70000+i*1000,0))
        c.targets["u1"]=f"t{i}"
        c.targets["u2"]=None; c.targets["u3"]=None
        c.state["u1"]=c.INTERCEPTING
        c.step(Obs(float(i),usvs),tracks,{},{},[],None,"NORMAL")
        c._pkg.clear()  # dissolve to allow re-form attempts
    assert c._formed_total==MAX_TOTAL_PACKAGES, c._formed_total
    print("test_budget_gate: PASS")
if __name__=="__main__":
    test_budget_cap()
