#!/usr/bin/env python
"""freeze_artifact.py — after 11/11 smoke PASS, write FROZEN_WAVE_REGISTRY.csv with bundle+adapter hashes."""
import csv, os
HERE=os.path.dirname(os.path.abspath(__file__))
FIELDS=["Wave","Short_ID","Registered_Name","Policy_ID","EntryPoint","Scenario_ID","Route_ID",
        "Artifact_SHA256","Adapter_SHA256","Smoke_Status"]
def main():
    with open(os.path.join(HERE,"..","FROZEN_WAVE_REGISTRY.csv"),"w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS); w.writeheader()
    print("FROZEN_WAVE_REGISTRY.csv (empty until freeze)")
if __name__=="__main__": main()
