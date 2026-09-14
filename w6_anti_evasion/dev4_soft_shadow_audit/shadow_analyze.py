#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""dev4_soft_shadow_audit/shadow_analyze.py — raw/unique grouping + temporal audit."""
import csv
import json
import os
import sys

OUT = os.path.dirname(os.path.abspath(__file__))


def load():
    recs = []
    for l in open(os.path.join(OUT, "shadow.jsonl")):
        try:
            recs.append(json.loads(l))
        except Exception:
            pass
    recs.sort(key=lambda r: (r["episode"], r["decision_index"]))
    return recs


def main():
    recs = load()
    # index proposals per decision
    per = {}
    total_dec = len(recs)
    for r in recs:
        ep = r["episode"]
        prop = {(p["p"], p["cur"], p["alt"]) for p in r.get("proposals", [])}
        soft_map = {s["p"]: (s["cur"], s.get("block"), s.get("alt"), s.get("alt_risk"))
                    for s in r.get("shadows", [])}
        per[(ep, r["sim_time"])] = {"prop": prop, "soft": soft_map, "t": r["sim_time"]}
    order = []
    for ep in sorted({k[0] for k in per}):
        evs = sorted([(t, k[1]) for k, (t) in [(k, per[k]["t"]) for k in per if k[0] == ep]])
    # simpler: flatten
    ev_list = []
    for ep in sorted({k[0] for k in per}):
        for (e0, t) in sorted([(k[1], per[k]["t"]) for k in per if k[0] == ep]):
            ev_list.append((ep, t))
    raw_total = sum(len(v["prop"]) for v in per.values())
    # unique grouping per (ep, platform, cur, alt) gap<=300s
    opts = []
    key_map = {}
    for (ep, t), v in per.items():
        for (p, cur, alt) in sorted(v["prop"]):
            k = (ep, p, cur, alt)
            if k not in key_map or (t - key_map[k][1]) > 300.0:
                opts.append({"episode": ep, "platform": p, "cur": cur, "alt": alt,
                             "start": t, "end": t, "raw": 1,
                             "seed": ep.rsplit("_", 1)[-1]})
                key_map[k] = (len(opts) - 1, t)
            else:
                idx, _ = key_map[k]
                opts[idx]["end"] = t
                opts[idx]["raw"] += 1
                key_map[k] = (idx, t)
    # stability: at start + {300,600,1200}, does same triplet still propose?
    times_by_ep = {}
    for k in per:
        times_by_ep.setdefault(k[0], []).append(per[k]["t"])
    for ep in times_by_ep:
        times_by_ep[ep].sort()
    import bisect
    def stable_flag(ep, start, plat, cur, alt):
        # look for the next decision time >= start+w within same episode
        ts = times_by_ep.get(ep, [])
        out = []
        for w in (300, 600, 1200):
            target = start + w
            # find nearest decision >= target
            i = bisect.bisect_left(ts, target)
            ok = None
            if i < len(ts):
                tgt_t = ts[i]
                key = (ep, tgt_t)
                if key in per and (plat, cur, alt) in per[key]["prop"]:
                    ok = True
                elif key in per:
                    # check if alt still high for platform
                    sm = per[key]["soft"].get(plat)
                    ok = bool(sm and sm[2] == alt)
            out.append(ok if ok is not None else False)
        return out
    n300 = n600 = n1200 = 0
    for o in opts:
        s3, s6, s12 = stable_flag(o["episode"], o["start"], o["platform"], o["cur"], o["alt"])
        o["stable300"] = s3; o["stable600"] = s6; o["stable1200"] = s12
        n300 += int(s3); n600 += int(s6); n1200 += int(s12)
    # blocked sampling
    blocked = []
    for (ep, t), v in per.items():
        for p, (cur, blk, alt, ar) in v["soft"].items():
            if blk not in (None, "PROPOSAL"):
                blocked.append({"episode": ep, "seed": ep.rsplit("_", 1)[-1],
                                "sim_time": t, "platform": p, "current_target": cur,
                                "block_reason": blk, "alt_risk": ar})
        if len(blocked) >= 200:
            break
    # write
    def wc(name, header, rows):
        with open(os.path.join(OUT, name), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=header); w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k) for k in header})
    raw_rows = []
    for (ep, t), v in per.items():
        for (p, cur, alt) in sorted(v["prop"]):
            sm = v["soft"].get(p, {})
            raw_rows.append({"episode": ep, "seed": ep.rsplit("_", 1)[-1], "sim_time": t,
                             "platform": p, "current_target": cur, "alternative_target": alt,
                             "reason": "PROTECTED_SOFT_PRIORITY_INVERSION"})
    wc("SHADOW_RAW_PROPOSALS.csv",
       ["episode", "seed", "sim_time", "platform", "current_target", "alternative_target", "reason"],
       raw_rows)
    wc("SHADOW_UNIQUE_OPPORTUNITIES.csv",
       ["opportunity_id", "seed", "platform", "current_target", "alternative_target",
        "start_time", "end_time", "duration", "raw_count", "stable300", "stable600",
        "stable1200"],
       [dict(o, opportunity_id=f"o{ix}", duration=round(o["end"] - o["start"], 1))
        for ix, o in enumerate(opts)])
    wc("SHADOW_BLOCKED_STATES.csv",
       ["episode", "seed", "sim_time", "platform", "current_target", "alt_risk", "block_reason"],
       blocked[:200])
    # frequency summary per run
    with open(os.path.join(OUT, "SHADOW_FREQUENCY_SUMMARY.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["metric", "value"])
        w.writerow(["runs", len({r["episode"] for r in recs})])
        w.writerow(["allocator_decisions", total_dec])
        w.writerow(["raw_proposals", raw_total])
        w.writerow(["raw_rate_per_decision", round(raw_total / max(1, total_dec), 4)])
        w.writerow(["unique_opportunities", len(opts)])
        w.writerow(["raw_over_unique", round(raw_total / max(1, len(opts)), 2)])
    # stability + reversal csv
    with open(os.path.join(OUT, "SHADOW_TEMPORAL_STABILITY.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["window", "stable_count", "fraction_of_unique"])
        for name, cnt in (("300", n300), ("600", n600), ("1200", n1200)):
            w.writerow([name, cnt, round(cnt / max(1, len(opts)), 3)])
    # attribution counts (risk-shift by definition all; prediction/pursuit/coverage recorded qualitatively)
    with open(os.path.join(OUT, "SHADOW_ATTRIBUTION.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["signal", "count"])
        w.writerow(["risk_shift(LOW/MED->HIGH+)", len(opts)])
        w.writerow(["stable600", n600])
    with open(os.path.join(OUT, "SHADOW_RUNTIME_OVERHEAD.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["metric", "value"])
        w.writerow(["shadow_decision_lines", total_dec])
        w.writerow(["mean_latency", "NOT_MEASURED_LIVE"])
    print("decisions:", total_dec)
    print("raw proposals:", raw_total, "rate/dec:", round(raw_total / max(1, total_dec), 4))
    print("unique opportunities:", len(opts), "raw/unique:", round(raw_total / max(1, len(opts)), 2))
    print("stable300:", n300, "stable600:", n600, "stable1200:", n1200)
    print("blocked sampled:", len(blocked))
    from collections import Counter
    print("block reasons:", Counter(b["block_reason"] for b in blocked))
    print("opts by seed:", Counter(o["seed"] for o in opts))
    print("duration mean (opts):", round(sum(o["end"] - o["start"] for o in opts) / max(1, len(opts)), 1))


if __name__ == "__main__":
    sys.exit(main())
