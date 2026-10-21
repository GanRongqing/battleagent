# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, "/root/autodl-tmp/hsystem")
import agent_hybrid_v5 as v5
from agent_hybrid_passive_recovery import PassiveAwareTrackManager

class O:
    def __init__(self, now, passive=(), active=()):
        self.now=now
        self.active=[{"name":n,"position":p,"velocity":v} for n,p,v in active]
        self.passive=[{"name":n,"bearing":b,"detected_by":d} for n,b,d in passive]
        self.usvs=[]; self.uavs=[]

def test_1_base_does_not_refresh_bearing():
    tm=v5.TrackManager()
    tm.update(O(0.0, passive=[("usv4",90.0,"white_usv1")]))
    tm.update(O(30.0, passive=[("usv4",45.0,"white_usv1")]))
    t=tm.tracks["usv4"]
    assert t.bearing==90.0, t.bearing            # BUG demonstrated: stale bearing
    assert t.last_seen_time==0.0, t.last_seen_time

def test_2_c15_refreshes_bearing():
    tm=PassiveAwareTrackManager()
    tm.update(O(0.0, passive=[("usv4",90.0,"white_usv1")]))
    tm.update(O(30.0, passive=[("usv4",45.0,"white_usv1")]))
    t=tm.tracks["usv4"]
    assert t.bearing==45.0, t.bearing
    assert t.last_seen_time==30.0

def test_3_never_promoted_to_positioned():
    tm=PassiveAwareTrackManager()
    tm.update(O(0.0, passive=[("usv4",90.0,"white_usv1")]))
    tm.update(O(30.0, passive=[("usv4",45.0,"white_usv1")]))
    assert tm.tracks["usv4"].has_position is False

def test_4_detector_memory():
    tm=PassiveAwareTrackManager()
    tm.update(O(0.0, passive=[("usv4",90.0,"white_usv1")]))
    tm.update(O(30.0, passive=[("usv4",80.0,"white_usv2")]))
    assert {"white_usv1","white_usv2"} <= tm.passive_detectors["usv4"]

def test_5_episode_isolation():
    a=PassiveAwareTrackManager(); a.update(O(0.0, passive=[("usv4",90.0,"white_usv1")]))
    b=PassiveAwareTrackManager()
    assert b.tracks=={} and b.passive_detectors=={}

def _all():
    fns=[v for k,v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    p=0
    for f in fns:
        try: f(); p+=1
        except Exception as e: print("FAIL",f.__name__,repr(e))
    print(f"passed={p}/{len(fns)}"); return p==len(fns)
if __name__=="__main__": sys.exit(0 if _all() else 1)
