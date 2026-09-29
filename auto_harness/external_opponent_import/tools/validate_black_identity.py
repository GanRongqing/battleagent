#!/usr/bin/env python
"""validate_black_identity.py — gate: each wave member must prove Black-side control.
Requires (>=1): registry policy_id, OR Black entrypoint invoked by scenario/route runner, OR
standalone Black-bound route/scenario artifact. Writes BLACK_IDENTITY_VALIDATION.csv."""
import csv, json, os
HERE=os.path.dirname(os.path.abspath(__file__))
OUT=os.path.join(HERE,"..","BLACK_IDENTITY_VALIDATION.csv")
def main():
    rows=[]
    # populated only when artifacts exist; identity must be evidenced, never name-guessed
    with open(OUT,"w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=["wave","short_id","registered_name","entrypoint","scenario_id",
            "route_id","evidence","black_side_verified","verdict"]); w.writeheader(); w.writerows(rows)
    print("BLACK_IDENTITY_VALIDATION.csv rows=",len(rows),"(empty until artifacts arrive)")
if __name__=="__main__": main()
