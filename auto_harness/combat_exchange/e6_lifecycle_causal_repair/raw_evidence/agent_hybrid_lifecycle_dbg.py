#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""agent_hybrid_lifecycle_dbg.py — LOGGING-ONLY wrapper (ACE) for E6 lifecycle causal tracing.

Wraps ExpandAgentMain; monkeypatches TrackManager.update / kill_detect and USVController.step to append
one JSONL record per macro-step with lifecycle/assignment/action state. It returns the ORIGINAL results,
so behaviour is unchanged (logger ON/OFF equivalence is checked separately).
Enable with env LIFE_DBG=<path>.
"""
import hashlib
import json
import os
import sys

import agent_hybrid_v5 as v5
from agent_hybrid_allocator_expand import ExpandAgentMain

_DBG = os.environ.get("LIFE_DBG", "/tmp/opencode/life_dbg.jsonl")
_ORIG_UPDATE = v5.TrackManager.update
_ORIG_KILLDETECT = v5.TrackManager.kill_detect
_ORIG_STEP = v5.USVController.step
_STATE = {"kill_events": [], "revives": [], "last_now": None}


def _update(self, obs):
    before = set(self.killed_names)
    # detect revive-on-active (OBS_TI_REVIVE) by diffing killed_names around the update
    out = _ORIG_UPDATE(self, obs)
    after = set(self.killed_names)
    revived = sorted(before - after)
    if revived:
        _STATE["revives"].append({"now": obs.now, "revived": revived})
    _STATE["last_killed"] = sorted(self.killed_names)
    _STATE["last_tracks"] = sorted(self.tracks.keys())
    return out


def _kill_detect(self, obs, prev_black_killed):
    before = set(self.killed_names)
    evs, killed = _ORIG_KILLDETECT(self, obs, prev_black_killed)
    added = sorted(set(self.killed_names) - before)
    if added:
        # reason: which heuristic fired (engaged_missing vs corpse)
        active = {e.get("name") for e in obs.active}
        reasons = []
        for n in added:
            t = self.tracks.get(n)
            reasons.append({"name": n, "in_active_now": n in active})
        _STATE["kill_events"].append({"now": obs.now, "added": added, "detail": reasons,
                                      "delta_black_killed": obs.black_killed - prev_black_killed})
    return evs, killed


def _step(self, obs, tracks, legal, alloc_result, events, intent=None, mission=None):
    acts = _ORIG_STEP(self, obs, tracks, legal, alloc_result, events, intent, mission)
    try:
        tgt = dict(getattr(self, "targets", {}))
        ah = hashlib.sha256(json.dumps([list(a) for a in acts], ensure_ascii=False).encode()).hexdigest()[:12]
        _STATE["revives"] = _STATE.get("revives", [])
        rec = {"now": obs.now,
               "killed_names": _STATE.get("last_killed", []),
               "tracks": _STATE.get("last_tracks", []),
               "assign": {k: v for k, v in tgt.items() if v},
               "action_hash": ah,
               "n_actions": len(acts),
               "revives_this_step": _STATE["revives"][-1]["revived"] if _STATE["revives"] and _STATE["revives"][-1]["now"] == obs.now else [],
               "kill_events_this_step": [k["added"] for k in _STATE["kill_events"] if k["now"] == obs.now]}
        with open(_DBG, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return acts


v5.TrackManager.update = _update
v5.TrackManager.kill_detect = _kill_detect
v5.USVController.step = _step


class LifeDbgAgentMain(ExpandAgentMain):
    pass


if __name__ == "__main__":
    use_uavs = True
    for a in sys.argv[1:]:
        if a == "--no-uav":
            use_uavs = False
    LifeDbgAgentMain(use_uavs=use_uavs).run()
