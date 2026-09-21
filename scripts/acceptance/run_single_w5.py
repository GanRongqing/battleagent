#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Acceptance: run ONE canonical frozen-W5 episode (S2 x B0_RANDOM, seed 1001, LLM off)."""
import os, sys, json, time
ROOT=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
import run_opponent_formal as rof
OUT=os.path.join(ROOT,'docs/acceptance_evidence/run'); os.makedirs(OUT, exist_ok=True)
rof.LOG_DIR=os.path.join(OUT,'logs'); os.makedirs(rof.LOG_DIR, exist_ok=True)
t0=time.time()
row=rof.run_one("ACCEPTANCE","S2","B0_RANDOM",1001)
row["wall_time_acceptance"]=round(time.time()-t0,1)
json.dump(row, open(os.path.join(OUT,'single_episode_result.json'),'w'), indent=2, default=str)
print(json.dumps({k:row.get(k) for k in ("scenario","opponent_profile","seed","result","clean_win","enemy_combat_killed_event","friendly_usv_dead","enemy_breakthrough_count","sim_time","wall_time_acceptance")}, default=str))
