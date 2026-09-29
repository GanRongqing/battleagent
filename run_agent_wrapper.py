#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""run_agent_wrapper.py — launch W5 or C1 against a specific API port WITHOUT modifying W5/C1.

Usage: python run_agent_wrapper.py <api_port> <w5|c1>

Behavior-neutral infra wrapper: only overrides the module-level API URL (the agent's `api()`
function reads the module-global `API` at call time). No policy logic is changed; W5/C1 sources
remain untouched.
"""
import sys

import agent_hybrid_v5 as w5

api_port = sys.argv[1]
agent = sys.argv[2]
w5.API = f"http://127.0.0.1:{api_port}"

if agent == "c1":
    from agent_hybrid_combat_c1 import CombatAgentMain
    CombatAgentMain(use_uavs=True).run()
elif agent == "prelock":
    from agent_hybrid_prelock_survival import PrelockSurvivalAgentMain
    PrelockSurvivalAgentMain(use_uavs=True).run()
elif agent == "lock":
    from agent_hybrid_lock_geometry import LockFirstAgentMain
    LockFirstAgentMain(use_uavs=True).run()
elif agent == "expand":
    from agent_hybrid_allocator_expand import ExpandAgentMain
    ExpandAgentMain(use_uavs=True).run()
elif agent == "reach":
    from agent_hybrid_reach_commit import ReachCommitAgentMain
    ReachCommitAgentMain(use_uavs=True).run()
else:
    w5.AgentMain(use_uavs=True).run()
