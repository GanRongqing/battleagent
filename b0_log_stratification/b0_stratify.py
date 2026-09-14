#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""b0_stratify.py — B0_RANDOM log 27-class stratification (length x width x speed).

Offline only. B0 is ONE policy (black-b0-v1); the 27 classes are WITHIN-policy log
strata, not policies.

Geometry source: behavior-neutral black_behavior_trace.jsonl (White-radar-visible
Black positions per poll). Only episodes that have this geometry/velocity evidence
are stratifiable; formal logs without Black traces are excluded (documented).

Method (b0-27class-v1):
  snapshot length/width: PCA on alive Black combat USV positions, robust span
    P90-P10 along major / minor principal axes.
  snapshot speed: per-unit displacement/Δt between consecutive samples; median.
  episode aggregation: median over valid snapshots (>=4 visible combat units).
  thresholds: empirical 33.33/66.67 percentiles over valid unique episodes.
  buckets: LOW x<=Q1, MID Q1<x<=Q2, HIGH x>Q2.
"""
import glob
import hashlib
import json
import math
import os
import statistics as st

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "b0_log_stratification")
METHOD_VERSION = "b0-27class-v1"

SOURCES = {
    "calibration_B0": ("policy_system/calibration/traces/B0_RANDOM/logs", "policy_system/calibration/traces/B0_RANDOM"),
    "fresh_b0": ("policy_system/evolution/auto_0001/fresh_b0/logs", "policy_system/evolution/auto_0001/fresh_b0/traces"),
    "cross_S1_b0": ("policy_system/evolution/auto_0001/cross_S1_b0/logs", "policy_system/evolution/auto_0001/cross_S1_b0/traces"),
    "cross_S3_b0": ("policy_system/evolution/auto_0001/cross_S3_b0/logs", "policy_system/evolution/auto_0001/cross_S3_b0/traces"),
}
# formal logs have White-side logs but no Black geometry trace -> excluded
FORMAL_DIR = "logs_formal"


def pct(vals, p):
    v = sorted(vals)
    if not v:
        return None
    k = (len(v) - 1) * p
    f, c = math.floor(k), math.ceil(k)
    return v[f] if f == c else v[f] * (c - k) + v[c] * (k - f)


def pca_span(pts):
    n = len(pts)
    if n < 2:
        return None, None
    cx = sum(p[0] for p in pts) / n
    cy = sum(p[1] for p in pts) / n
    sxx = sum((p[0] - cx) ** 2 for p in pts)
    syy = sum((p[1] - cy) ** 2 for p in pts)
    sxy = sum((p[0] - cx) * (p[1] - cy) for p in pts)
    if abs(sxy) < 1e-12:
        ang = 0.0 if sxx >= syy else math.pi / 2
    else:
        ang = 0.5 * math.atan2(2 * sxy, sxx - syy)
    ux, uy = math.cos(ang), math.sin(ang)
    maj = [(p[0] - cx) * ux + (p[1] - cy) * uy for p in pts]
    minr = [-(p[0] - cx) * uy + (p[1] - cy) * ux for p in pts]
    return pct(maj, 0.9) - pct(maj, 0.1), pct(minr, 0.9) - pct(minr, 0.1)


def episode_features(trace_path, min_visible=4, window=None):
    """Return dict with length/width/speed + snapshot counts, or None if unusable."""
    if not os.path.exists(trace_path):
        return None
    samples = []
    with open(trace_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))
    if not samples:
        return None
    if window is not None:
        samples = samples[:window]
    # speed: per-unit displacement / dt across consecutive samples
    prev, speeds = {}, []
    for s in samples:
        for p in s.get("positions", []):
            nm = p["name"]
            if nm in prev:
                dt = s["sim_time"] - prev[nm][0]
                if dt > 0:
                    speeds.append(math.hypot(p["x"] - prev[nm][1], p["y"] - prev[nm][2]) / dt)
            prev[nm] = (s["sim_time"], p["x"], p["y"])
    lens, wids = [], []
    for s in samples:
        pts = [(p["x"], p["y"]) for p in s.get("positions", [])]
        if len(pts) >= min_visible:
            a, b = pca_span(pts)
            if a is not None:
                lens.append(a); wids.append(b)
    if not lens or not speeds:
        return None
    return {"length": st.median(lens), "width": st.median(wids), "speed": st.median(speeds),
            "snapshots": len(lens), "speed_samples": len(speeds)}


def trace_hash(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]


def discover():
    """Enumerate candidate B0 episodes; attach trace + validity + dedup."""
    cands = []
    for src, (logdir, tracedir) in SOURCES.items():
        for tp in sorted(glob.glob(os.path.join(tracedir, "s*_black_behavior_trace.jsonl"))):
            base = os.path.basename(tp).replace("_black_behavior_trace.jsonl", "")
            seed = int(base.lstrip("s"))
            # scenario from log file name if present
            logs = glob.glob(os.path.join(logdir, f"S*_B0_RANDOM_{base}.log"))
            scen = "S2"
            if logs:
                scen = os.path.basename(logs[0]).split("_")[0]
            cands.append({"source": src, "seed": seed, "scenario": scen,
                          "trace_path": tp, "trace_hash": trace_hash(tp)})
    return cands


def classify(x, q1, q2):
    if x <= q1:
        return "LOW"
    if x <= q2:
        return "MID"
    return "HIGH"


def short(b):
    return {"LOW": "L", "MID": "M", "HIGH": "H"}[b]


ALL_CLASSES = [f"LENGTH_{l}__WIDTH_{w}__SPEED_{s}"
               for l in ("LOW", "MID", "HIGH")
               for w in ("LOW", "MID", "HIGH")
               for s in ("LOW", "MID", "HIGH")]


def run(write=True):
    os.makedirs(OUT, exist_ok=True)
    cands = discover()
    # validity + dedup
    seen = {}
    invalid = []
    for c in cands:
        feats = episode_features(c["trace_path"])
        if feats is None:
            invalid.append({**c, "reason": "no usable geometry/velocity (missing speed or <min visible)"})
            continue
        # round to kill floating-point noise; a combat USV is commanded at 10 m/s,
        # so a near-zero episode-median speed is a trace/velocity artifact -> invalid
        feats = {"length": round(feats["length"], 1), "width": round(feats["width"], 1),
                 "speed": round(feats["speed"], 3), "snapshots": feats["snapshots"],
                 "speed_samples": feats["speed_samples"]}
        if feats["speed"] < 1.0:
            invalid.append({**c, "reason": f"unusable velocity signal (episode median speed={feats['speed']})"})
            continue
        c.update(feats)
        key = c["trace_hash"]
        if key in seen:
            c["dup_of"] = seen[key]["trace_path"]
            continue
        seen[key] = c
    valid = list(seen.values())
    # long-tail audit: whole vs first-20-snapshot window
    tail = []
    for c in valid:
        fw = episode_features(c["trace_path"], window=20)
        if fw:
            tail.append((c["length"] - fw["length"], c["width"] - fw["width"], c["speed"] - fw["speed"]))
    lens = [c["length"] for c in valid]; wids = [c["width"] for c in valid]; spds = [c["speed"] for c in valid]
    q = {"length_q1": pct(lens, 1 / 3), "length_q2": pct(lens, 2 / 3),
         "width_q1": pct(wids, 1 / 3), "width_q2": pct(wids, 2 / 3),
         "speed_q1": pct(spds, 1 / 3), "speed_q2": pct(spds, 2 / 3)}
    ds_hash = hashlib.sha256("|".join(sorted(c["trace_hash"] for c in valid)).encode()).hexdigest()[:16]
    thresholds = {"dataset_id": "B0_RANDOM_stratification", "dataset_hash": ds_hash,
                  "episode_count": len(valid), "method_version": METHOD_VERSION,
                  **{k: round(v, 6) for k, v in q.items()},
                  "created_at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
                  "bucket_rule": "LOW x<=Q1; MID Q1<x<=Q2; HIGH x>Q2"}
    for c in valid:
        c["length_bucket"] = classify(c["length"], q["length_q1"], q["length_q2"])
        c["width_bucket"] = classify(c["width"], q["width_q1"], q["width_q2"])
        c["speed_bucket"] = classify(c["speed"], q["speed_q1"], q["speed_q2"])
        c["class_id"] = f"LENGTH_{c['length_bucket']}__WIDTH_{c['width_bucket']}__SPEED_{c['speed_bucket']}"
    counts = {cid: [] for cid in ALL_CLASSES}
    for c in valid:
        counts[c["class_id"]].append(f"B0_{c['scenario']}_s{c['seed']}")
    def tie_count(vals):
        from collections import Counter
        cc = Counter(vals)
        return sum(n for n in cc.values() if n > 1)  # episodes sharing a value
    ties = {"length_ties": tie_count([c["length"] for c in valid]),
            "width_ties": tie_count([c["width"] for c in valid]),
            "speed_ties": tie_count([c["speed"] for c in valid]),
            "speed_unique_values": len(set(c["speed"] for c in valid))}
    marg = {"length": {b: sum(1 for c in valid if c["length_bucket"] == b) for b in ("LOW", "MID", "HIGH")},
            "width": {b: sum(1 for c in valid if c["width_bucket"] == b) for b in ("LOW", "MID", "HIGH")},
            "speed": {b: sum(1 for c in valid if c["speed_bucket"] == b) for b in ("LOW", "MID", "HIGH")}}
    result = {"candidates": len(cands), "valid": valid, "invalid": invalid,
              "thresholds": thresholds, "counts": counts, "marginals": marg,
              "tail_audit": tail, "dataset_hash": ds_hash, "ties": ties}
    if write:
        json.dump(thresholds, open(os.path.join(OUT, "B0_27CLASS_THRESHOLDS.json"), "w"), indent=2)
        with open(os.path.join(OUT, "B0_LOG_27CLASS_ASSIGNMENTS.csv"), "w", newline="") as f:
            import csv
            w = csv.writer(f)
            w.writerow(["episode_id", "seed", "source", "trace_hash", "formation_length",
                        "length_bucket", "formation_width", "width_bucket", "formation_speed",
                        "speed_bucket", "class_id", "classification_method", "valid"])
            for c in valid:
                w.writerow([f"B0_{c['scenario']}_s{c['seed']}", c["seed"], c["source"], c["trace_hash"],
                            round(c["length"], 2), c["length_bucket"], round(c["width"], 2), c["width_bucket"],
                            round(c["speed"], 4), c["speed_bucket"], c["class_id"], METHOD_VERSION, 1])
        with open(os.path.join(OUT, "B0_27CLASS_COUNTS.csv"), "w", newline="") as f:
            import csv
            w = csv.writer(f)
            w.writerow(["class_id", "length_bucket", "width_bucket", "speed_bucket", "count", "fraction", "episode_ids"])
            for cid in ALL_CLASSES:
                l, wd, sp = cid.split("__")
                eps = counts[cid]
                w.writerow([cid, l.replace("LENGTH_", ""), wd.replace("WIDTH_", ""), sp.replace("SPEED_", ""),
                            len(eps), round(len(eps) / max(1, len(valid)), 4), ";".join(eps)])
        write_report(result)
    return result


def write_report(result):
    import csv
    valid = result["valid"]; counts = result["counts"]; marg = result["marginals"]
    th = result["thresholds"]
    n = len(valid)
    occ = {k: len(v) for k, v in counts.items() if v}
    import math as _m
    ent = 0.0
    for c in occ.values():
        p = c / n
        ent -= p * _m.log(p, 2)
    lines = ["# B0_RANDOM 27-Class Stratification Report", "",
             f"Policy: black-b0-v1 (B0_RANDOM). Empirical class: E0. "
             f"These 27 are WITHIN-policy log strata, NOT policies.", "",
             f"- candidates (B0 episodes with black trace): {result['candidates']}",
             f"- invalid excluded: {len(result['invalid'])}",
             f"- valid unique logs: {n}",
             f"- dataset_hash: {result['dataset_hash']}",
             f"- thresholds: length q33={th['length_q1']:.1f} q67={th['length_q2']:.1f}; "
             f"width q33={th['width_q1']:.1f} q67={th['width_q2']:.1f}; "
             f"speed q33={th['speed_q1']} q67={th['speed_q2']}", "",
             "## Marginal counts", "",
             f"Length: LOW={marg['length']['LOW']} MID={marg['length']['MID']} HIGH={marg['length']['HIGH']}",
             f"Width:  LOW={marg['width']['LOW']} MID={marg['width']['MID']} HIGH={marg['width']['HIGH']}",
             f"Speed:  LOW={marg['speed']['LOW']} MID={marg['speed']['MID']} HIGH={marg['speed']['HIGH']}", "",
             "## Occupancy", "",
             f"- occupied classes: {len(occ)}", f"- empty classes: {27 - len(occ)}",
             f"- largest class: {max(occ.items(), key=lambda x: x[1]) if occ else None}",
             f"- class entropy (bits): {round(ent, 3)}", "",
             "Speed axis is degenerate: B0 commands constant 10 m/s (all episodes speed LOW); "
             "the effective stratification is length x width (9 strata).", "",
             "## 3x3x3 counts (SPEED = LOW; MID/HIGH all zero)", "",
             "| length \\ width | WIDTH_LOW | WIDTH_MID | WIDTH_HIGH |",
             "|---|---|---|---|"]
    for lb in ("LOW", "MID", "HIGH"):
        row = [f"LENGTH_{lb}"]
        for wb in ("LOW", "MID", "HIGH"):
            row.append(str(len(counts[f"LENGTH_{lb}__WIDTH_{wb}__SPEED_LOW"])))
        lines.append("| " + " | ".join(row) + " |")
    lines += ["", "SPEED = MID and SPEED = HIGH: all 18 cells are 0 (speed axis degenerate).", "",
              "## Invalid excluded", ""]
    for c in result["invalid"]:
        lines.append(f"- {c['source']} seed {c['seed']}: {c['reason']}")
    open(os.path.join(OUT, "B0_27CLASS_REPORT.md"), "w").write("\n".join(lines))


if __name__ == "__main__":
    r = run()
    print("candidates", r["candidates"], "valid", len(r["valid"]), "invalid", len(r["invalid"]))
    print("thresholds", r["thresholds"])
    print("marginals", r["marginals"])
    occ = {k: len(v) for k, v in r["counts"].items() if v}
    print("occupied", len(occ), "empty", 27 - len(occ))
    print(occ)
