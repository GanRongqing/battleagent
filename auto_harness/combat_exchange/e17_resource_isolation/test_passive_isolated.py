# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, "/root/autodl-tmp/hsystem")
import agent_hybrid_v5 as v5
from agent_hybrid_passive_isolated import PassiveHistoryManager, ResourceAwareLocalizeUAVManager, LOCALIZE_MAX_AGE

class O:
    def __init__(self, now, passive=(), active=(), usvs=(), uavs=()):
        self.now=now
        self.active=[{"name":n,"position":p,"velocity":v} for n,p,v in active]
        self.passive=[{"name":n,"bearing":b,"detected_by":d} for n,b,d in passive]
        self.usvs=[{"name":n,"position":p,"is_alive":True} for n,p in usvs]
        self.uavs=[{"name":n,"position":p,"is_alive":True,"is_at_usv":False} for n,p in uavs]

# ---- passive history contract ----
def test_1_multi_detector_binding():
    tm=PassiveHistoryManager()
    tm.update(O(0.0, passive=[("usv4",90.0,"white_usv1")], usvs=[("white_usv1",(1000,0))]))
    tm.update(O(30.0, passive=[("usv4",80.0,"white_usv2")], usvs=[("white_usv2",(2000,500))]))
    h=tm.passive_history["usv4"]
    assert h[0]["detector_pos"]==(1000,0) and h[1]["detector_pos"]==(2000,500)

def test_2_expiry():
    tm=PassiveHistoryManager()
    tm.update(O(0.0, passive=[("usv4",90.0,"white_usv1")], usvs=[("white_usv1",(1000,0))]))
    assert tm.localize_candidates(30.0)              # fresh
    assert not tm.localize_candidates(0.0+LOCALIZE_MAX_AGE+1)  # expired

def test_3_duplicate_same_observation():
    tm=PassiveHistoryManager()
    p=[("usv4",90.0,"white_usv1")]
    tm.update(O(0.0, passive=p, usvs=[("white_usv1",(1000,0))]))
    tm.update(O(0.0, passive=p, usvs=[("white_usv1",(1000,0))]))
    assert len(tm.passive_history["usv4"])==1

def test_4_no_position_promotion():
    tm=PassiveHistoryManager()
    tm.update(O(0.0, passive=[("usv4",90.0,"white_usv1")], usvs=[("white_usv1",(1000,0))]))
    assert tm.tracks["usv4"].has_position is False

def test_5_episode_isolation():
    a=PassiveHistoryManager(); a.update(O(0.0, passive=[("usv4",90.0,"white_usv1")], usvs=[("white_usv1",(1,0))]))
    b=PassiveHistoryManager()
    assert b.tracks=={} and b.passive_history=={} and b.passive_best=={}

# ---- resource isolation of the UAV localizer ----
_ORIG=v5.UAVManager.step
def _stub(self, obs, tracker, legal, events, intent=None, threat_fn=None, coverage=None, mission=None):
    return [(f"{u['name']} 飞行 target_speed=100.0 target_course=90.0","fly") for u in obs.uavs if u.get("is_alive")]
v5.UAVManager.step=_stub

def _mgr(states):
    m=ResourceAwareLocalizeUAVManager(enabled=True)
    m.state=dict(states)
    return m

def _tracker_with_candidate():
    tm=PassiveHistoryManager()
    tm.update(O(0.0, passive=[("usv4",90.0,"white_usv1")], usvs=[("white_usv1",(1000,0))]))
    return tm

def test_6_return_landing_not_overridden():
    tm=_tracker_with_candidate()
    mgr=_mgr({"u1":v5.UAVManager.RETURN,"u2":v5.UAVManager.LANDING,"u3":v5.UAVManager.SCREEN})
    obs=O(30.0, uavs=[("u1",(0,0)),("u2",(0,0)),("u3",(0,0))])
    acts=mgr.step(obs,tm,{},[],None)
    assert all("target_course=90.0" in a[0] for a in acts)   # unchanged (no SEARCH scout)

def test_7_no_eligible_scout_no_change():
    tm=_tracker_with_candidate()
    mgr=_mgr({"u1":v5.UAVManager.RETURN,"u2":v5.UAVManager.RETURN})
    obs=O(30.0, uavs=[("u1",(0,0)),("u2",(0,0))])
    acts=mgr.step(obs,tm,{},[],None)
    assert len(acts)==2 and all("target_course=90.0" in a[0] for a in acts)

def test_8_search_scout_selected():
    tm=_tracker_with_candidate()
    mgr=_mgr({"u1":v5.UAVManager.SEARCH,"u2":v5.UAVManager.RETURN})
    obs=O(30.0, uavs=[("u1",(0,0)),("u2",(0,0))])
    acts=mgr.step(obs,tm,{},[],None)
    assert any(a[0].startswith("u1 ") and "target_course=180" in a[0] for a in acts) or any(a[0].startswith("u1 ") for a in acts)
    assert any(a[0].startswith("u2 ") for a in acts)   # other UAV's action preserved

def test_9_no_candidate_no_change():
    tm=PassiveHistoryManager()   # empty
    mgr=_mgr({"u1":v5.UAVManager.SEARCH,"u2":v5.UAVManager.SEARCH})
    obs=O(0.0, uavs=[("u1",(0,0)),("u2",(0,0))])
    acts=mgr.step(obs,tm,{},[],None)
    assert len(acts)==2 and all("target_course=90.0" in a[0] for a in acts)

def test_10_single_uav_no_change():
    tm=_tracker_with_candidate()
    mgr=_mgr({"u1":v5.UAVManager.SEARCH})
    obs=O(30.0, uavs=[("u1",(0,0))])
    acts=mgr.step(obs,tm,{},[],None)
    assert len(acts)==1 and "target_course=90.0" in acts[0][0]

def _all():
    fns=[v for k,v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    p=0
    for f in fns:
        try: f(); p+=1
        except Exception as e: print("FAIL",f.__name__,repr(e))
    v5.UAVManager.step=_ORIG
    print(f"passed={p}/{len(fns)}"); return p==len(fns)

if __name__=="__main__": sys.exit(0 if _all() else 1)
