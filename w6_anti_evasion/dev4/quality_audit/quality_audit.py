#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""dev4/quality_audit/quality_audit.py — audit real dev4 reallocations + local consequences."""
import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
OUT = os.path.dirname(os.path.abspath(__file__))
DEV4 = os.path.join(ROOT, "w6_anti_evasion", "dev4")


def load_events():
    return [json.loads(l) for l in open(os.path.join(DEV4, "dev4_events.jsonl"))]


def load_trail():
    trail = []
    for l in open(os.path.join(DEV4, "dev4_trail.jsonl")):
        try:
            trail.append(json.loads(l))
        except Exception:
            pass
    return trail


def snap_after(trail, ep, t):
    """first trail entry at >= t for episode ep."""
    best = None
    for r in trail:
        if r["episode"] == ep and r["sim_time"] >= t:
            if best is None or r["sim_time"] < best["sim_time"]:
                best = r
    return best


def main():
    events = load_events()
    trail = load_trail()
    rows = []
    for i, e in enumerate(events):
        ep = e["episode"]; t = e["sim_time"]; p = e["platform"]; new = e["new_target"]
        rows.append({"idx": i, "seed": e["seed"], "type": e["type"], "platform": p,
                     "old": e.get("old_target"), "new": new, "reason": e["reason"],
                     "dest_eta": e.get("dest_eta"), "lead_eta": e.get("lead_eta"),
                     "sim_time": t})
        res = {}
        for w in (300, 600, 1200):
            s = snap_after(trail, ep, t + w)
            if s is None:
                res[w] = {"alive": None, "target": None}
                continue
            u = s["units"].get(p, {})
            res[w] = {"alive": bool(u.get("a", True)), "target": u.get("t"),
                      "locking": bool(u.get("l"))}
        # persistence / reversal / death / lock heuristics
        s300 = res[300]; s600 = res[600]; s1200 = res[1200]
        alive_at_600 = s600["alive"] if s600["alive"] is not None else True
        target_at_300 = s300["target"]
        on_new_300 = (target_at_300 == new) if target_at_300 is not None else False
        released_300 = (target_at_300 is None and s300["alive"])
        locked_1200 = bool(s1200.get("locking"))
        dead_300 = (s300["alive"] is False)
        dead_600 = (s600["alive"] is False)
        # verdict (decision-local only)
        de = e.get("dest_eta"); le = e.get("lead_eta")
        worse_than_lead = (de is not None and le is not None and de > 2.0 * le)
        if dead_300 or dead_600:
            verdict = "BAD"
        elif released_300:
            verdict = "BAD"            # released within 300s -> churn/pointless
        elif worse_than_lead and not locked_1200 and not on_new_300:
            verdict = "BAD"
        elif on_new_300 and alive_at_600:
            # persisted and engaged on an imminent target
            verdict = "GOOD"
        elif locked_1200 and alive_at_600:
            verdict = "GOOD"
        elif on_new_300 is False and s300["alive"] is None:
            verdict = "AMBIGUOUS"
        else:
            verdict = "NEUTRAL"
        rows[-1].update({"persist300_on_new": on_new_300, "released300": released_300,
                         "locked1200": locked_1200, "dead300": dead_300,
                         "dead600": dead_600, "alive600": alive_at_600,
                         "worse_than_lead": worse_than_lead, "verdict": verdict})
    # write CSV
    with open(os.path.join(OUT, "LIVE_REALLOCATION_EVENTS.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["idx"])
        w.writeheader(); w.writerows(rows)
    with open(os.path.join(OUT, "LIVE_REALLOCATION_QUALITY.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["idx"])
        w.writeheader(); w.writerows(rows)
    from collections import Counter
    print("events:", len(rows))
    print("verdicts:", Counter(r["verdict"] for r in rows))
    print("types:", Counter(r["type"] for r in rows))
    print("dead300:", sum(1 for r in rows if r["dead300"]),
          "dead600:", sum(1 for r in rows if r["dead600"]),
          "released300:", sum(1 for r in rows if r["released300"]),
          "locked1200:", sum(1 for r in rows if r["locked1200"]),
          "worse_than_lead:", sum(1 for r in rows if r["worse_than_lead"]))
    for r in rows:
        print(f"  e{r['idx']} s{r['seed']} {r['type'][:8]:<8} {r['platform']}->{r['new']} "
              f"reason={r['reason'][:16]:<16} persist300={r['persist300_on_new']} "
              f"dead={r['dead300'] or r['dead600']} lock1200={r['locked1200']} => {r['verdict']}")


if __name__ == "__main__":
    sys.exit(main())
