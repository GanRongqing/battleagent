#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""b0v2_stratify.py — independent 27-class stratification for black-b0-v2.

Reuses the FROZEN B0-v1 definitions (PCA P90-P10 span; episode median actual combat
speed) from b0_log_stratification/b0_stratify.py. B0-v2 thresholds are computed
INDEPENDENTLY (no v1 thresholds, no v1+v2 mixing).
"""
import csv
import glob
import json
import math
import os
import statistics as st
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "b0_log_stratification"))
import b0_stratify as b1  # noqa: E402

OUT = os.path.join(ROOT, "b0_v2")
ALL = b1.ALL_CLASSES
METHOD_VERSION = "b0v2-27class-v1"


def discover(dataset_dir, seeds=None):
    rows = []
    ep = os.path.join(dataset_dir, "EPISODES.csv")
    valid_seeds = set()
    if os.path.exists(ep):
        for r in csv.DictReader(open(ep)):
            if r.get("http_or_trace_errors") not in (None, "", "0", 0) or str(r.get("agent_rc")) not in ("0", "", "None"):
                continue
            valid_seeds.add(int(r["seed"]))
    want = set(int(s) for s in seeds) if seeds else None
    for tp in sorted(glob.glob(os.path.join(dataset_dir, "traces", "s*_black_behavior_trace.jsonl"))):
        seed = int(os.path.basename(tp).split("_")[0].lstrip("s"))
        if valid_seeds and seed not in valid_seeds:
            continue
        if want is not None and seed not in want:
            continue
        rows.append({"seed": seed, "trace_path": tp, "trace_hash": b1.trace_hash(tp)})
    return rows


def run(dataset_dir, tag="B0_V2", seeds=None):
    cands = discover(dataset_dir, seeds)
    valid, invalid, seen = [], [], {}
    for c in cands:
        feats = b1.episode_features(c["trace_path"])
        if feats is None:
            invalid.append({**c, "reason": "no usable geometry/velocity"}); continue
        feats = {"length": round(feats["length"], 1), "width": round(feats["width"], 1),
                 "speed": round(feats["speed"], 3)}
        if feats["speed"] < 1.0:
            invalid.append({**c, "reason": f"unusable velocity (median {feats['speed']})"}); continue
        if c["trace_hash"] in seen:
            continue
        seen[c["trace_hash"]] = True
        c.update(feats); valid.append(c)
    lens = [c["length"] for c in valid]; wids = [c["width"] for c in valid]; spds = [c["speed"] for c in valid]
    q = {"length_q1": b1.pct(lens, 1/3), "length_q2": b1.pct(lens, 2/3),
         "width_q1": b1.pct(wids, 1/3), "width_q2": b1.pct(wids, 2/3),
         "speed_q1": b1.pct(spds, 1/3), "speed_q2": b1.pct(spds, 2/3)}
    ds_hash = __import__("hashlib").sha256("|".join(sorted(c["trace_hash"] for c in valid)).encode()).hexdigest()[:16]
    for c in valid:
        c["length_bucket"] = b1.classify(c["length"], q["length_q1"], q["length_q2"])
        c["width_bucket"] = b1.classify(c["width"], q["width_q1"], q["width_q2"])
        c["speed_bucket"] = b1.classify(c["speed"], q["speed_q1"], q["speed_q2"])
        c["class_id"] = f"LENGTH_{c['length_bucket']}__WIDTH_{c['width_bucket']}__SPEED_{c['speed_bucket']}"
    counts = {cid: [] for cid in ALL}
    for c in valid:
        counts[c["class_id"]].append(f"B0V2_S2_s{c['seed']}")
    marg = {ax: {b: sum(1 for c in valid if c[ax+"_bucket"] == b) for b in ("LOW", "MID", "HIGH")}
            for ax in ("length", "width", "speed")}
    n = len(valid)
    occ = {k: len(v) for k, v in counts.items() if v}
    ent = -sum((c/n)*math.log(c/n, 2) for c in occ.values()) if n else 0
    thresholds = {"dataset_id": f"{tag}_stratification", "dataset_hash": ds_hash,
                  "episode_count": n, "method_version": METHOD_VERSION,
                  **{k: round(v, 6) for k, v in q.items()},
                  "created_at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
                  "bucket_rule": "LOW x<=Q1; MID Q1<x<=Q2; HIGH x>Q2",
                  "speed_axis_non_degenerate": q["speed_q1"] < q["speed_q2"]}
    json.dump(thresholds, open(os.path.join(OUT, "B0_V2_27CLASS_THRESHOLDS.json"), "w"), indent=2)
    with open(os.path.join(OUT, "B0_V2_27CLASS_ASSIGNMENTS.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["episode_id", "seed", "trace_hash", "formation_length", "length_bucket",
                    "formation_width", "width_bucket", "formation_speed", "speed_bucket",
                    "class_id", "classification_method", "valid"])
        for c in valid:
            w.writerow([f"B0V2_S2_s{c['seed']}", c["seed"], c["trace_hash"], c["length"], c["length_bucket"],
                        c["width"], c["width_bucket"], c["speed"], c["speed_bucket"], c["class_id"],
                        METHOD_VERSION, 1])
    with open(os.path.join(OUT, "B0_V2_27CLASS_COUNTS.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["class_id", "length_bucket", "width_bucket", "speed_bucket", "count", "fraction", "episode_ids"])
        for cid in ALL:
            l, wd, sp = cid.split("__")
            eps = counts[cid]
            w.writerow([cid, l.replace("LENGTH_", ""), wd.replace("WIDTH_", ""), sp.replace("SPEED_", ""),
                        len(eps), round(len(eps)/max(1, n), 4), ";".join(eps)])
    lines = [f"# B0-v2 27-Class Report ({tag}, N={n})", "",
             (f"**N={n} is used to validate the three-axis percentile classification and the "
              f"class distribution; it is NOT used to claim sufficient statistical coverage of "
              f"all 27 classes.**" if n == 27 else ""), "",
             f"- independent thresholds: length q33={q['length_q1']:.1f} q67={q['length_q2']:.1f}; "
             f"width q33={q['width_q1']:.1f} q67={q['width_q2']:.1f}; "
             f"speed q33={q['speed_q1']} q67={q['speed_q2']}",
             f"- speed axis non-degenerate = {q['speed_q1'] < q['speed_q2']}", "",
             f"Length: LOW={marg['length']['LOW']} MID={marg['length']['MID']} HIGH={marg['length']['HIGH']}",
             f"Width:  LOW={marg['width']['LOW']} MID={marg['width']['MID']} HIGH={marg['width']['HIGH']}",
             f"Speed:  LOW={marg['speed']['LOW']} MID={marg['speed']['MID']} HIGH={marg['speed']['HIGH']}", "",
             f"occupied={len(occ)} empty={27-len(occ)} largest={max(occ.items(), key=lambda x:x[1]) if occ else None} entropy={round(ent,3)}", ""]
    for sp in ("LOW", "MID", "HIGH"):
        lines += [f"## SPEED = {sp}", "", "| length \\ width | WIDTH_LOW | WIDTH_MID | WIDTH_HIGH |", "|---|---|---|---|"]
        for lb in ("LOW", "MID", "HIGH"):
            row = [f"LENGTH_{lb}"]
            for wb in ("LOW", "MID", "HIGH"):
                c = len(counts[f"LENGTH_{lb}__WIDTH_{wb}__SPEED_{sp}"])
                row.append(f"{c} ({round(c/max(1,n),3)})")
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")
    lines += ["## Invalid excluded", ""] + [f"- seed {c['seed']}: {c['reason']}" for c in invalid]
    open(os.path.join(OUT, "B0_V2_27CLASS_REPORT.md"), "w").write("\n".join(lines))
    return {"n": n, "thresholds": thresholds, "counts": counts, "marginals": marg,
            "occupied": len(occ), "empty": 27-len(occ), "entropy": round(ent, 3),
            "valid": valid, "invalid": invalid}


if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else os.path.join(OUT, "full")
    r = run(d)
    print(json.dumps({k: r[k] for k in ("n", "thresholds", "marginals", "occupied", "empty", "entropy")}, indent=2))
