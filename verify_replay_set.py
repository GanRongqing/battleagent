#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""verify_replay_set.py — verify a two-sided replay bundle has both sides per episode."""
import glob, json, os, sys

d = sys.argv[1] if len(sys.argv) > 1 else "/root/reports/replay_set_b0_s2"
files = sorted(glob.glob(os.path.join(d, "replay", "replay_s*.jsonl")))
print("episodes:", len(files))
ok = True
for fp in files:
    recs = [json.loads(l) for l in open(fp) if l.strip()]
    n = len(recs)
    has_w = any(r.get("white_usv") for r in recs)
    has_uav = any(r.get("white_uav") for r in recs)
    has_b = any(r.get("black_visible") for r in recs)
    wmax = max((len(r.get("white_usv", [])) for r in recs), default=0)
    bmax = max((len(r.get("black_visible", [])) for r in recs), default=0)
    good = n > 0 and has_w and has_b
    ok = ok and good
    print(f"  {os.path.basename(fp)}: samples={n} white_usv={has_w}(max {wmax}) "
          f"white_uav={has_uav} black_visible={has_b}(max {bmax}) -> {'OK' if good else 'MISSING'}")
print("BOTH SIDES PRESENT:", "PASS" if ok else "FAIL")
