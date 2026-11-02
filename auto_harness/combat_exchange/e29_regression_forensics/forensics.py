# -*- coding: utf-8 -*-
"""E29 forensic extractor (read-only). Usage:
  python forensics.py <run_dir> <sid> <policy> [--times 00:10:00,00:30:00]
Prints K/L, first active contact / first own-lock / first White loss, and mean USV (x,y) km at given times.
"""
import json, glob, os, sys
run, sid, pol = sys.argv[1], sys.argv[2], sys.argv[3]
times = sys.argv[5].split(",") if len(sys.argv) > 5 and sys.argv[4] == "--times" else ["00:10:00","00:30:00","00:50:00","01:10:00"]
r=None
for f in glob.glob(f"/tmp/opencode/parallel_runs/{run}/results/*.json"):
    j=json.load(open(f))
    if j["Strategy"]==sid and j["Policy"]==pol: r=j["Result"]
p=None
for w in os.listdir(f"/tmp/opencode/parallel_runs/{run}"):
    q=f"/tmp/opencode/parallel_runs/{run}/{w}/api_logs/games/{r['Game_Log']}"
    if os.path.exists(q): p=q
d=json.load(open(p))
fa=fl=floss=None; samples={}
for s in d["steps"]:
    t=s["episode_time"]
    if fa is None and s.get("active_enemies"): fa=t
    if fl is None and any(u.get("is_locking") for u in s.get("usv_states",[])): fl=t
    us=[u for u in s.get("usv_states",[]) if u.get("is_alive") and u.get("position")]
    if us and t in times:
        samples[t]=(round(sum(u["position"][0] for u in us)/len(us)/1000,1),
                    round(sum(u["position"][1] for u in us)/len(us)/1000,1))
    for e in (s.get("events") or []):
        if floss is None and e.startswith("white_usv") and "被击毁" in e: floss=t
print(f"{sid} {pol}: K/L={r['Black_Killed']}/{r['White_USV_Lost']} firstActive={fa} firstOwnLock={fl} firstWhiteLoss={floss}")
print("mean(x,y)km:", samples)
