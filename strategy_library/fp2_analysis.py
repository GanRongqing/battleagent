#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""fp2_analysis.py — fp-v2 per-seed CSV, aggregates, pairwise behavioral/
response difference, Cohen's d, paired deltas, direction consistency, reports.

Runs AFTER common calibration episodes complete (B0-B3 x 7001-7010, S2 W5).
Honesty: only shared numerically-available features enter a comparison;
unavailable != 0. Behavior and response never merged into one number.
"""
import csv
import itertools
import json
import math
import os
import statistics

try:
    from . import policy_fp2 as fp2
except ImportError:
    import policy_fp2 as fp2

ROOT = fp2._ROOT
CAL = os.path.join(ROOT, "policy_system", "calibration")
ANALYSIS = os.path.join(CAL, "analysis")
os.makedirs(ANALYSIS, exist_ok=True)

PROFILES = fp2.PROFILES
SEEDS = fp2.SEEDS

BEHAVIORAL_ORDER = ["temporal", "spatial", "coordination", "adaptation"]


def flat_numeric(fp, block):
    """Flatten {block:{grp:{feat:{value,availability}}}} -> list of
    (fqn, grp, feat, value, availability) for numeric values."""
    out = []
    for grp, feats in fp.get(block, {}).items():
        if not isinstance(feats, dict):
            continue
        for feat, meta in feats.items():
            if not isinstance(meta, dict) or "availability" not in meta:
                continue
            v = meta.get("value")
            avail = (meta.get("availability") if isinstance(meta, dict) else None) or []
            if isinstance(v, (int, float)):
                a = avail[0] if isinstance(avail, list) and avail else str(avail)
                out.append((f"{grp}.{feat}", grp, feat, float(v), a))
    return out


def load_all():
    ep = fp2.load_episodes()
    all_fps = {}
    for prof in PROFILES:
        fps = []
        for sd in SEEDS:
            if (prof, sd) in ep:
                row = ep[(prof, sd)]
                http_err = row.get("http_or_trace_errors")
                rc = row.get("agent_rc")
                if (http_err not in (None, "", "0", 0)) or (str(rc) not in ("0", "", "None")):
                    continue
                fps.append(fp2.episode_fp(prof, sd, row, fp2.load_trace(prof, sd)))
        all_fps[prof] = fps
    return all_fps


def per_seed_table(all_fps):
    path = os.path.join(ANALYSIS, "POLICY_BEHAVIOR_FEATURES_PER_SEED.csv")
    fqn = {}
    for prof in PROFILES:
        fps = all_fps[prof]
        if not fps:
            continue
        for b in ("behavioral", "response"):
            for (name, grp, feat, v, a) in flat_numeric(fps[0], b):
                fqn[(b, grp, feat)] = True
    cols = ["policy_id", "seed", "block", "group", "feature", "availability", "value"]
    rows = []
    for prof in PROFILES:
        for f in all_fps[prof]:
            for b in ("behavioral", "response"):
                for (name, grp, feat, v, a) in flat_numeric(f, b):
                    rows.append([prof, f["seed"], b, grp, feat, a, v])
    rows.sort()
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(rows)
    return path


def aggregate_table(all_fps):
    path = os.path.join(ANALYSIS, "POLICY_BEHAVIOR_FEATURES_V2.csv")
    rows = []
    for prof in PROFILES:
        if not all_fps[prof]:
            continue
        agg = fp2.aggregate_fingerprint(prof, all_fps[prof])
        for block in ("behavioral", "response"):
            for grp in agg[block]:
                for feat, meta in agg[block][grp].items():
                    avail = "|".join(agg["availability"].get(f"{grp}.{feat}", []))
                    rows.append([prof, agg["episode_count"], block, grp, feat, avail,
                                 meta.get("mean"), meta.get("std"), meta.get("median"),
                                 meta.get("p25"), meta.get("p75"), meta.get("n")])
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["policy_id", "n", "block", "group", "feature", "availability",
                    "mean", "std", "median", "p25", "p75", "n_used"])
        w.writerows(rows)
    return path


def per_seed_values(all_fps, prof, block):
    """feature -> {seed: value} for numeric available entries."""
    out = {}
    for f in all_fps[prof]:
        for (name, grp, feat, v, a) in flat_numeric(f, block):
            if a == "unavailable":
                continue
            out.setdefault(name, {})[f["seed"]] = v
    return out


def pair_analysis(pa, pb, all_fps):
    """Behavioral and response paired comparison across shared seeds."""
    res = {"policy_a": pa, "policy_b": pb,
           "behavioral": {}, "response": {}, "n": 0}
    bA, bB = per_seed_values(all_fps, pa, "behavioral"), per_seed_values(all_fps, pb, "behavioral")
    rA, rB = per_seed_values(all_fps, pa, "response"), per_seed_values(all_fps, pb, "response")
    sA = {f["seed"] for f in all_fps[pa]}
    sB = {f["seed"] for f in all_fps[pb]}
    seeds = sorted(sA & sB)
    res["n"] = len(seeds)

    def compare(mapsA, mapsB):
        out = []
        for feat in sorted(set(mapsA) & set(mapsB)):
            va = [mapsA[feat].get(s) for s in seeds]
            vb = [mapsB[feat].get(s) for s in seeds]
            na = [x for x in va if x is not None]
            nb = [x for x in vb if x is not None]
            if len(na) < 2 or len(nb) < 2:
                continue
            ma, mb = statistics.mean(na), statistics.mean(nb)
            sd = math.sqrt((statistics.pstdev(na) ** 2 + statistics.pstdev(nb) ** 2) / 2) or 1e-9
            d = (mb - ma) / sd
            deltas = [b - a for a, b in zip(va, vb) if a is not None and b is not None]
            sign_consist = (sum(1 for x in deltas if x > 0) / len(deltas)
                            if deltas else None)
            out.append({"feature": feat, "mean_a": round(ma, 4), "mean_b": round(mb, 4),
                        "delta_mean": round(mb - ma, 4),
                        "delta_median": round(statistics.median([b - a for a, b in
                                                                 zip(na, nb)]), 4),
                        "cohens_d": round(d, 3),
                        "direction_consistency": round(sign_consist, 3) if sign_consist is not None else None,
                        "n_seeds": len(deltas)})
        out.sort(key=lambda x: abs(x["cohens_d"]), reverse=True)
        return out

    res["behavioral"] = compare(bA, bB)
    res["response"] = compare(rA, rB)
    return res


def global_dist(pa, pb, all_fps):
    """Standardized behavioral and response distances over shared features."""
    def _gd(block):
        mA, mB = per_seed_values(all_fps, pa, block), per_seed_values(all_fps, pb, block)
        dsum, wsum = 0.0, 0.0
        for feat in sorted(set(mA) & set(mB)):
            va = [mA[feat].get(s) for s in mA[feat]] + [mB[feat].get(s) for s in mB[feat]]
            vals = [x for x in va if x is not None]
            if len(vals) < 4 or statistics.pstdev(vals) == 0:
                continue
            dsum += abs(statistics.mean([mB[feat].get(s) for s in mB[feat] if mB[feat].get(s) is not None])
                        - statistics.mean([mA[feat].get(s) for s in mA[feat] if mA[feat].get(s) is not None])) \
                / statistics.pstdev(vals)
            wsum += 1.0
        return round(dsum / wsum, 3) if wsum else None
    return {"behavioral_distance": _gd("behavioral"), "response_distance": _gd("response")}


def run(all_fps=None):
    all_fps = all_fps or load_all()
    for prof in PROFILES:
        print(prof, "n=", len(all_fps[prof]))
    per_seed_table(all_fps)
    aggregate_table(all_fps)
    # response signature summary table
    rp = os.path.join(ANALYSIS, "POLICY_RESPONSE_SIGNATURES.csv")
    with open(rp, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["policy_id", "n", "response_group", "feature", "mean", "std", "median"])
        for prof in PROFILES:
            if not all_fps[prof]:
                continue
            agg = fp2.aggregate_fingerprint(prof, all_fps[prof])
            for grp in agg["response"]:
                for feat, meta in agg["response"][grp].items():
                    w.writerow([prof, agg["episode_count"], grp, feat,
                                meta.get("mean"), meta.get("std"), meta.get("median")])
    return all_fps


if __name__ == "__main__":
    af = run()
    pairs = list(itertools.combinations(PROFILES, 2))
    for pa, pb in pairs:
        pr = pair_analysis(pa, pb, af)
        gd = global_dist(pa, pb, af)
        print(pa, "vs", pb, "beh_top=",
              pr["behavioral"][:3] if pr["behavioral"] else "none",
              "resp=", (pr["response"][:1] if pr["response"] else "none"),
              "dist=", gd)
