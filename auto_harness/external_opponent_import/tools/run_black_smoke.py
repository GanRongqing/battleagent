#!/usr/bin/env python
"""run_black_smoke.py — 1 episode per opponent under deterministic step mode.
Runs ONLY after 5/5 + 6/6 static pass. White=ACE, Black=external. Fix seed e.g. 41001.
Writes SMOKE_RESULTS.csv with load/init/action/runtime/terminal/determinism PASS flags."""
import csv, os, sys
HERE=os.path.dirname(os.path.abspath(__file__))
FIELDS=["Wave","Strategy","Seed","Load_PASS","Init_PASS","Black_Action_PASS","Runtime_PASS",
        "Terminal_PASS","Determinism_PASS","Valid","Notes"]
def main():
    reg=os.path.join(HERE,"..","external_wave_registry.json")
    rows=[]
    print("run_black_smoke: no runnable registry yet (artifacts missing)")
    with open(os.path.join(HERE,"..","SMOKE_RESULTS.csv"),"w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
if __name__=="__main__": main()
