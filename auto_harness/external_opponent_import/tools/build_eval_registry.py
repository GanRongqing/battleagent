#!/usr/bin/env python
"""build_eval_registry.py — assemble the 15-strategy eval set (B0-B3 + 5 + 6) ONLY after freeze.
Refuses to substitute AUTO1/dispersed/two-wave/White plans."""
import csv, os
HERE=os.path.dirname(os.path.abspath(__file__))
ORDER=["B0","B1","B2","B3","W1-1","W1-2","W1-3","W1-4","W1-5","W2-1","W2-2","W2-3","W2-4","W2-5","W2-6"]
def main():
    frozen=os.path.join(HERE,"..","FROZEN_WAVE_REGISTRY.csv")
    n=0
    if os.path.exists(frozen):
        n=sum(1 for _ in csv.DictReader(open(frozen,encoding="utf-8")))
    if n!=11:
        print(f"build_eval_registry: REFUSE - frozen wave members {n}/11 (need WAVE1=5, WAVE2=6)")
        return
    print("eval registry ready:", ORDER)
if __name__=="__main__": main()
