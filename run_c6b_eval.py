#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""run_c6b_eval.py — C6B (pre-lock admission) paired eval W2-1/W2-6 hard + W2-2/W2-4 control."""
import argparse,csv,json,os,re,subprocess,time
ROOT=os.path.dirname(os.path.abspath(__file__))
OUT=os.path.join(ROOT,"auto_harness","combat_exchange","c6b_prelock_admission"); RAW=os.path.join(OUT,"raw_logs")
PY="/root/miniconda3/envs/hsystem_env/bin/python"; SEEDFILE="/tmp/opencode/seed_w0.txt"
STRATS=[("W2-1","横向编队-中央汇聚箭头突防"),("W2-6","菱形编队-MUSV外侧绕行SUSV中央收缩"),
        ("W2-2","菱形编队-接近后扇形展开突防"),("W2-4","菱形编队-南北两翼镜像夹击")]
FIELDS=["Strategy","Registered_Name","Seed","Valid","Black_Kills","White_USV_Losses","White_UAV_Losses","CER","Exchange_Result","Terminal_Result","Sim_Time","Wall_Time","First_Death","Alive_End"]
def meta(t):
    g=lambda k:(re.search(rf"\[META\].*?\b{k}=(\S+)",t) or [None,None])[1] if re.search(rf"\[META\].*?\b{k}=(\S+)",t) else None
    m=re.search(r"\[META\] result=(\S+)",t)
    return {"result":m.group(1) if m else "UNFINISHED","ek":g("enemy_kills"),"ul":g("friendly_usv_losses"),"uav":g("friendly_uav_losses")}
def first_death_alive(text):
    fd=None; alive_end=None
    for ln in text.splitlines():
        m=re.match(r"^\[t=([\d,]+)s\] step=\d+ \|.*?USV: (\d+)/(\d+)",ln)
        if m:
            t=int(m.group(1).replace(",","")); a=int(m.group(2))
            if a<int(m.group(3)) and fd is None: fd=t
            alive_end=a
    return fd,alive_end
def run_one(sid,scen,seed,port):
    logf=os.path.join(RAW,f"C6B_{sid}_seed{seed}.log"); open(SEEDFILE,"w").write(str(seed))
    env=dict(os.environ); env["SCENARIO_SCRIPT"]=scen; env["LLM_ENABLED"]="false"; env["PYTHONUNBUFFERED"]="1"
    t0=time.time()
    with open(logf,"w") as f:
        p=subprocess.Popen([PY,"run_agent_wrapper.py",str(port),"admit"],cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT); p.wait()
    wall=round(time.time()-t0,1); text=open(logf,encoding="utf-8",errors="replace").read(); m=meta(text)
    fd,ae=first_death_alive(text); valid="[META]" in text
    k=int(m["ek"]) if m["ek"] else 0; l=int(m["ul"]) if m["ul"] else 0; uav=int(m["uav"]) if m["uav"] else 0
    return {"Strategy":sid,"Registered_Name":scen,"Seed":seed,"Valid":valid,"Black_Kills":k,"White_USV_Losses":l,
            "White_UAV_Losses":uav,"CER":(round(k/l,3) if l else ("K:0" if k==0 else "inf")),
            "Exchange_Result":("EXCHANGE_WIN" if k>l else ("EXCHANGE_TIE" if k==l else "EXCHANGE_LOSS")),
            "Terminal_Result":m["result"],"Sim_Time":"","Wall_Time":wall,"First_Death":fd,"Alive_End":ae}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--seeds",default="43001,43002,43003,43004,43005"); ap.add_argument("--port",type=int,default=8000)
    a=ap.parse_args(); seeds=[int(s) for s in a.seeds.split(",")]; os.makedirs(RAW,exist_ok=True); rows=[]
    for sid,scen in STRATS:
        for seed in seeds:
            r=run_one(sid,scen,seed,a.port); rows.append(r); print(json.dumps(r,ensure_ascii=False),flush=True)
            with open(os.path.join(OUT,"09_C6B_EPISODES.csv"),"w",newline="",encoding="utf-8") as f:
                w=csv.DictWriter(f,fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
    print("DONE",len(rows))
if __name__=="__main__": main()
