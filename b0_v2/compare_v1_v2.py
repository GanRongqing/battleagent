#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""compare_v1_v2.py — black-b0-v1 vs black-b0-v2 comparison + fp + E0 retention."""
import csv
import json
import os
import statistics as st
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "strategy_library"))
sys.path.insert(0, os.path.join(ROOT, "b0_log_stratification"))
import b0_stratify as b1  # noqa: E402
import b0v2_stratify as b2  # noqa: E402
import strategy_library.policy_fp2 as fp2  # noqa: E402
import strategy_library.fp2_analysis as fa  # noqa: E402

OUT = os.path.join(ROOT, "b0_v2")


def dist_summary(vals):
    if not vals:
        return {}
    return {"n": len(vals), "mean": round(st.mean(vals), 3), "median": round(st.median(vals), 3),
            "std": round(st.pstdev(vals), 3), "min": round(min(vals), 3), "max": round(max(vals), 3),
            "unique": len(set(round(v, 3) for v in vals))}


def v2_fps(dataset_dir, seeds=None):
    ep = os.path.join(dataset_dir, "EPISODES.csv")
    rows = {}
    if os.path.exists(ep):
        for r in csv.DictReader(open(ep)):
            if r.get("http_or_trace_errors") in (None, "", "0", 0):
                if seeds is None or int(r["seed"]) in set(seeds):
                    rows[int(r["seed"])] = r
    old = fp2.TRACES
    fp2.TRACES = os.path.join(dataset_dir, "traces")
    fps = []
    for s, r in sorted(rows.items()):
        fps.append(fp2.episode_fp("B0_V2", s, r, fp2.load_trace("B0_V2", s)))
    fp2.TRACES = old
    return fps


def run(v2_dir, seeds=None):
    r1 = b1.run(write=False)          # B0-v1 (28 valid, frozen)
    r2 = b2.run(v2_dir, seeds=seeds)  # B0-v2 independent
    v1sp = [c["speed"] for c in r1["valid"]]
    v2sp = [c["speed"] for c in r2["valid"]]
    cmp = {"v1_speed": dist_summary(v1sp), "v2_speed": dist_summary(v2sp),
           "v1_length": dist_summary([c["length"] for c in r1["valid"]]),
           "v2_length": dist_summary([c["length"] for c in r2["valid"]]),
           "v1_width": dist_summary([c["width"] for c in r1["valid"]]),
           "v2_width": dist_summary([c["width"] for c in r2["valid"]]),
           "v1_occupied": 9, "v2_occupied": r2["occupied"],
           "v1_speed_degenerate": r1["thresholds"]["speed_q1"] == r1["thresholds"]["speed_q2"],
           "v2_speed_degenerate": r2["thresholds"]["speed_q1"] == r2["thresholds"]["speed_q2"]}
    # fingerprint distance v1 vs v2
    af = fa.load_all()  # B0..B3 from common calibration (S2 7001-7010)
    allf = {"B0_RANDOM": af.get("B0_RANDOM", []), "B0_V2": v2_fps(v2_dir, seeds)}
    try:
        gd = fa.global_dist("B0_RANDOM", "B0_V2", allf)
    except Exception as e:
        gd = {"error": str(e)}
    cmp["behavior_distance_v1_v2"] = gd.get("behavioral_distance")
    cmp["response_distance_v1_v2"] = gd.get("response_distance")
    # response signature v2
    resp = {}
    if allf["B0_V2"]:
        agg = fp2.aggregate_fingerprint("B0_V2", allf["B0_V2"])
        resp = {k: m.get("mean") for k, m in agg["response"].get("outcomes", {}).items()}
    cmp["v2_response"] = resp
    json.dump(cmp, open(os.path.join(OUT, "B0_V1_VS_V2_COMPARISON.json"), "w"), indent=2)
    lines = ["# B0-v1 vs B0-v2 Comparison", "",
             "## Q1 Why v1 speed axis degenerate?", "",
             f"- B0-v1 commands fixed 10 m/s (= ShipMotorTZB.max_speed); v1 speed std="
             f"{cmp['v1_speed'].get('std')}, unique={cmp['v1_speed'].get('unique')} -> q33==q67.",
             "", "## Q2 How v2 introduces legal speed variance?", "",
             "- black-b0-v2 samples episode_target_speed ~ Uniform(5,10) m/s (deterministic, "
             "separate RNG stream); same waypoint logic as v1.", "",
             "## Q3 Actual speed variance?", "",
             f"- v2 speed: {cmp['v2_speed']}", f"- v2 speed degenerate = {cmp['v2_speed_degenerate']}", "",
             "## Q4 Random/uncoordinated identity?", "",
             "- no coordination/adaptation/phase logic (unit tests + source audit); "
             "E0 retention via fp (no structured replan/phase features).", "",
             "## Q5 Occupied classes", "",
             f"- v1 occupied={cmp['v1_occupied']} (speed degenerate); v2 occupied={cmp['v2_occupied']}", "",
             "## Q6 Marginals", "",
             f"- v1 length {r1['marginals']['length']}, width {r1['marginals']['width']}, speed {r1['marginals']['speed']}",
             f"- v2 length {r2['marginals']['length']}, width {r2['marginals']['width']}, speed {r2['marginals']['speed']}", "",
             "## Q7 Empty cells", "",
             f"- v2 empty={r2['empty']}/27 (feature correlation / sparse N; not forced).", "",
             "## Behavior/response distance v1 vs v2", "",
             f"- behavior_distance={cmp['behavior_distance_v1_v2']} response_distance={cmp['response_distance_v1_v2']}",
             f"- v2 response signature: {resp}", "",
             "## Q8 Should v2 enter active pool?", "",
             "- Recommendation pending full N=90 + fp; v2 is a baseline variant, not a new class.", "",
             "## Q9 black-b0 alias", "",
             "- Keep alias on v1 for now; consider v2 only after validation (not auto-switched)."]
    open(os.path.join(OUT, "B0_V1_VS_V2_COMPARISON.md"), "w").write("\n".join(lines))
    return cmp


if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else os.path.join(OUT, "full")
    print(json.dumps(run(d, seeds=list(range(9001, 9028))), indent=2))
