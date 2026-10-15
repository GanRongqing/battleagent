#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""agent_hybrid_obs_dbg.py — LOGGING-ONLY wrapper around C11 (SpareSupport).

Writes one JSONL record per agent step: obs.active names/positions, obs.passive names,
TrackManager track names. It does NOT change any action (calls the original step and returns its
result). Used to reconcile the agent's legal observation against the game-log active_enemies.
Enable with env OBS_DBG=<path> (default /tmp/opencode/obs_dbg.jsonl).
"""
import json
import os
import sys

import agent_hybrid_spare_support as base

_ORIG = base.SpareSupportController.step


def _step(self, obs, tracks, legal, alloc_result, events, intent=None, mission=None):
    acts = _ORIG(self, obs, tracks, legal, alloc_result, events, intent, mission)
    try:
        rec = {
            "now": obs.now,
            "active": [{"name": e.get("name"), "position": e.get("position")} for e in (obs.active or [])],
            "passive": [e.get("name") for e in (obs.passive or [])],
            "tracks": {n: (getattr(t, "has_position", False), getattr(t, "last_seen_time", None))
                       for n, t in (tracks or {}).items()},
            "formed": len(self._pkg),
        }
        with open(os.environ.get("OBS_DBG", "/tmp/opencode/obs_dbg.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return acts


base.SpareSupportController.step = _step


class ObsDbgAgentMain(base.SpareSupportAgentMain):
    pass


if __name__ == "__main__":
    use_uavs = True
    for a in sys.argv[1:]:
        if a == "--no-uav":
            use_uavs = False
    ObsDbgAgentMain(use_uavs=use_uavs).run()
