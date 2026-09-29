#!/usr/bin/env python
"""recover_entrypoints.py — from STATIC_AUDIT candidates, propose entrypoint/route/scenario.
Read-only. Writes ENTRYPOINT_CANDIDATES.json."""
import csv, json, os
HERE=os.path.dirname(os.path.abspath(__file__))
def main():
    src=os.path.join(HERE,"..","STATIC_AUDIT.csv")
    out={}
    if os.path.exists(src):
        for r in csv.DictReader(open(src,encoding="utf-8")):
            out[r["source_path"]]={"entrypoint":r["entrypoint_candidate"],
                                   "route":r["route_candidate"],"scenario":r["scenario_candidate"],
                                   "classification":r["classification"]}
    json.dump(out,open(os.path.join(HERE,"..","ENTRYPOINT_CANDIDATES.json"),"w"),indent=1,ensure_ascii=False)
    print("ENTRYPOINT_CANDIDATES.json",len(out))
if __name__=="__main__": main()
