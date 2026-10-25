# -*- coding: utf-8 -*-
"""E20 read-only evidence audit (never feeds the online Agent).
Reproduces: step dt, active/passive windows, min White-USV -> positioned-Black distance,
C17 UAV death battery, observation funnel for W2-1 vs W2-4.
Usage: python audit.py <run_dir> <sid> <policy>
"""
import json, glob, os, math, sys

def load(run, sid, pol):
    r = None
    for f in glob.glob(f"/tmp/opencode/parallel_runs/{run}/results/*.json"):
        j = json.load(open(f))
        if j["Strategy"] == sid and j["Policy"] == pol:
            r = j["Result"]
    p = None
    for w in os.listdir(f"/tmp/opencode/parallel_runs/{run}"):
        q = f"/tmp/opencode/parallel_runs/{run}/{w}/api_logs/games/{r['Game_Log']}"
        if os.path.exists(q):
            p = q
    return r, json.load(open(p))

def funnel(run, sid, pol):
    r, d = load(run, sid, pol)
    ts = d["steps"]
    def sec(s):
        h, m, x = s.split(":"); return int(h)*3600+int(m)*60+float(x)
    dt = sorted({sec(ts[i+1]["episode_time"])-sec(ts[i]["episode_time"]) for i in range(min(20, len(ts)-1))})
    act = sum(1 for s in ts if s.get("active_enemies"))
    pas = sum(1 for s in ts if s.get("passive_enemies"))
    maxa = max((len(s.get("active_enemies") or []) for s in ts), default=0)
    maxp = max((len(s.get("passive_enemies") or []) for s in ts), default=0)
    first_act = next((s["episode_time"] for s in ts if s.get("active_enemies")), None)
    mind = 1e18
    for s in ts:
        ae = [e for e in (s.get("active_enemies") or []) if e.get("position")]
        for u in s.get("usv_states", []):
            if not (u.get("is_alive") and u.get("position")): continue
            for e in ae:
                dd = math.hypot(u["position"][0]-e["position"][0], u["position"][1]-e["position"][1])
                mind = min(mind, dd)
    return dict(sid=sid, steps=len(ts), dt=dt, active_steps=act, passive_steps=pas,
                max_active=maxa, max_passive=maxp, first_active=first_act,
                min_usv_black_km=round(mind/1000, 1) if mind < 1e17 else None,
                kills=r["Black_Killed"], losses=r["White_USV_Lost"])

if __name__ == "__main__":
    run = sys.argv[1] if len(sys.argv) > 1 else "e9_B_c10_off"
    for sid in (sys.argv[2:] or ["W2-1", "W2-4"]):
        pol = "C10" if run == "e9_B_c10_off" else "C17"
        print(funnel(run, sid, pol))
