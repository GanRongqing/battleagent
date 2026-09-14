#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""run_b0_v2.py — collect black-b0-v2 episodes with geometry/actual-speed trace."""
import argparse, csv, json, os, shutil, sys, time
ROOT=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,ROOT)
import run_opponent_formal as rof
from common_policy_calibration import _sampler
B0V2_META="/tmp/opencode/b0v2_meta.json"

def load_done(p):
    if not os.path.exists(p): return set()
    try: return {int(r["seed"]) for r in csv.DictReader(open(p)) if r.get("seed")}
    except Exception: return set()

def run(seeds, out_dir, exp_id):
    os.makedirs(out_dir, exist_ok=True)
    rof.LOG_DIR=os.path.join(out_dir,"logs"); os.makedirs(rof.LOG_DIR,exist_ok=True)
    tr=os.path.join(out_dir,"traces"); os.makedirs(tr,exist_ok=True)
    ep=os.path.join(out_dir,"EPISODES.csv"); done=load_done(ep); new=not os.path.exists(ep)
    f=open(ep,"a",newline="",encoding="utf-8"); w=csv.DictWriter(f,fieldnames=rof.COLS)
    if new: w.writeheader(); f.flush()
    for sd in seeds:
        if sd in done: print(f"[SKIP] s{sd}",flush=True); continue
        print(f"[START] s{sd} {time.strftime('%H:%M:%S')}",flush=True)
        for pth in (B0V2_META,): 
            if os.path.exists(pth): os.remove(pth)
        tp=os.path.join(tr,f"s{sd}_black_behavior_trace.jsonl")
        if os.path.exists(tp): os.remove(tp)
        samp_t,samp_stop=_sampler(tp); samp_t.start()
        try: row=rof.run_one(exp_id,"S2","B0_V2_VARIABLE_SPEED",sd)
        except Exception as e:
            row={c:None for c in rof.COLS}; row["opponent_profile"]="B0_V2_VARIABLE_SPEED"; row["seed"]=sd
            row["http_or_trace_errors"]=1; row["agent_rc"]=-1; print("[ABNORMAL]",e,flush=True)
        finally:
            samp_stop.set(); samp_t.join(timeout=6)
        meta={}
        if os.path.exists(B0V2_META):
            shutil.copy(B0V2_META,os.path.join(tr,f"s{sd}_b0v2_meta.json"))
            try: meta=json.load(open(B0V2_META))
            except Exception: meta={}
        wall=float(row.get("wall_time") or 0)
        if (wall<20 and row.get("result")=="UNFINISHED") or row.get("http_or_trace_errors"):
            print(f"  -> ABNORMAL excluded wall={wall}s",flush=True); continue
        w.writerow({k:row.get(k) for k in rof.COLS}); f.flush()
        print(f"  -> {row.get('result')} clean={row.get('clean_win')} target_speed={meta.get('episode_target_speed')} wall={wall}s",flush=True)
    f.close(); print(f"[done] {len(load_done(ep))}",flush=True)

if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--seeds",nargs="*",type=int,required=True)
    ap.add_argument("--out-dir",required=True); ap.add_argument("--experiment-id",default="B0V2")
    a=ap.parse_args(); run(a.seeds,a.out_dir,a.experiment_id)
