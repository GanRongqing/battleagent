#!/usr/bin/env python
"""classify_artifacts.py — static, read-only audit of each candidate artifact.
Writes STATIC_AUDIT.csv. Does NOT run any artifact code."""
import csv, os, re
INC="/root/sc2agent/incoming_opponents"; EXT=os.path.join(INC,"extracted")
OUT=os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","STATIC_AUDIT.csv")
UNSAFE=[("os.system","shell exec"),("subprocess","process spawn"),("socket","network"),
        ("requests","network"),("urllib","network"),("shutil.rmtree","delete"),
        ("os.remove","delete"),("open(\"/","abs write"),("os.environ[","env mutation"),
        ("get_black_targets",None),("hidden","hidden-truth"),("future","future-truth")]
BLACK_HINTS=re.compile(r"black|BLUE|enemy|opponent|waypoint|红方|蓝方|黑方")
ENTRY_HINTS=re.compile(r"def (build|sim|apply|step|reset|paths|waypoints|main|run)\b")
def classify(txt):
    low=txt.lower()
    unsafe=[n for n,d in UNSAFE if n.lower() in low and d]
    if any(s in low for s in ["os.system","subprocess","socket.","requests.","shutil.rmtree","os.remove("]):
        return "UNSAFE",unsafe
    if "white_usv_states" in low or "tracks" in low and "black" not in low:
        return "WHITE_POLICY",unsafe
    if BLACK_HINTS.search(txt): return "BLACK_OPPONENT_CANDIDATE",unsafe
    if ENTRY_HINTS.search(txt): return "UTILITY",unsafe
    return "UNKNOWN",unsafe
def main():
    rows=[]
    for wave in ("wave1","wave2"):
        for dp,_,fs in os.walk(os.path.join(EXT,wave)):
            for fn in fs:
                if not fn.endswith((".py",".json")): continue
                p=os.path.join(dp,fn)
                try: txt=open(p,encoding="utf-8",errors="replace").read()
                except Exception: continue
                cls,unsafe=classify(txt)
                rows.append({"wave":wave,"candidate_id":fn,"source_path":os.path.relpath(p,EXT),
                             "declared_name":"","entrypoint_candidate":";".join(ENTRY_HINTS.findall(txt)[:5]),
                             "route_candidate":"route" if "route" in txt.lower() else "",
                             "scenario_candidate":"scenario" if "scenario" in txt.lower() else "",
                             "config_candidate":"config" if "config" in txt.lower() else "",
                             "black_side_evidence":"yes" if BLACK_HINTS.search(txt) else "no",
                             "hidden_truth_risk":"yes" if "future" in txt.lower() else "no",
                             "external_dependency":"","unsafe_behavior":";".join(unsafe),
                             "classification":cls,"confidence":"low"})
    with open(OUT,"w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=["wave","candidate_id","source_path","declared_name","entrypoint_candidate",
            "route_candidate","scenario_candidate","config_candidate","black_side_evidence","hidden_truth_risk",
            "external_dependency","unsafe_behavior","classification","confidence"]); w.writeheader(); w.writerows(rows)
    print("STATIC_AUDIT.csv rows=",len(rows))
if __name__=="__main__": main()
