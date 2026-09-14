#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""seed_calibration_fp2.py — finalize fp-v2 common calibration.

Runs AFTER B0-B3 x 7001-7010 episodes complete:
  1. writes fingerprints/<policy>_fp-v2.json (full fp-v2 payload)
  2. DB: add fp-v2 EmpiricalFingerprint per policy (fp-v1 preserved)
  3. DB: add 6 pair fp-v2 ValidationRecords with behavioral/response verdicts
  4. CSVs: per-seed, aggregate features, response signatures, difference matrix
  5. Markdown pair reports (all 6), distance calibration, declared-vs-empirical,
     final common-calibration report, historical-formal consistency
"""
import csv
import itertools
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from strategy_library import fp2_analysis as fa
    from strategy_library import policy_fp2 as fp2
    from strategy_library.policy_models import EmpiricalFingerprint, ValidationRecord
    from strategy_library.policy_repository import get_policy_repository
except Exception:
    from strategy_library import fp2_analysis as fa  # noqa
    from strategy_library import policy_fp2 as fp2  # noqa

ROOT = fp2._ROOT
CAL = os.path.join(ROOT, "policy_system", "calibration")
FPDIR = os.path.join(CAL, "fingerprints")
ANALYSIS = os.path.join(CAL, "analysis")
os.makedirs(FPDIR, exist_ok=True)

PROFILES = fp2.PROFILES
SEEDS = fp2.SEEDS
PROFILE_TO_PID = {"B0_RANDOM": "black-b0-v1", "B1_MULTI_AXIS": "black-b1-v1",
                  "B2_COORDINATED_PRESSURE": "black-b2-v1", "B3_ADAPTIVE": "black-b3-v1"}
PID_TO_PROFILE = {v: k for k, v in PROFILE_TO_PID.items()}


def collect_stats(feat_map, seeds):
    vals = [feat_map[s] for s in seeds if s in feat_map and feat_map[s] is not None]
    if not vals:
        return {"mean": None, "median": None, "std": None, "n": 0}
    return {"mean": round(statistics.mean(vals), 3),
            "median": round(statistics.median(vals), 3),
            "std": round(statistics.pstdev(vals), 3) if len(vals) > 1 else 0.0,
            "n": len(vals)}


def verdict_for(pair, af):
    """Final pairwise verdict logic per task spec (S2 common calibration)."""
    pa, pb = pair
    na, nb = len(af[pa]), len(af[pb])
    if min(na, nb) < 10:
        return {"behavior": "INSUFFICIENT", "response": "INSUFFICIENT",
                "multi_seed": "insufficient", "verdict": "INSUFFICIENT_EVIDENCE"}
    pr = fa.pair_analysis(pa, pb, af)
    gd = fa.global_dist(pa, pb, af)
    beh, resp = pr["behavioral"], pr["response"]
    bd, rd = gd.get("behavioral_distance"), gd.get("response_distance")
    # behavioral distinctness: strong top effect + direction stability
    strong = [x for x in beh if x["direction_consistency"] is not None and x["direction_consistency"] >= 0.8 and abs(x["cohens_d"]) >= 1.0]
    weak_beh = bool(beh) and not strong
    beh_stable = any(x["direction_consistency"] is not None for x in beh) and bool(strong) and (bd is not None and bd > 0.3)
    beh_verdict = "distinct" if beh_stable else ("inconclusive" if weak_beh or beh else "insufficient")
    resp_verdict = "distinct" if (rd is not None and rd > 0.3) else "similar"
    if beh_verdict == "distinct":
        final = "EMPIRICALLY_DISTINCT"
    elif beh_verdict == "insufficient":
        final = "INSUFFICIENT_EVIDENCE"
    else:
        final = "INCONCLUSIVE"
    return {"na": na, "nb": nb,
            "behavioral_top": strong[:5] if strong else beh[:5],
            "behavior_distance": bd, "response_distance": rd,
            "behavior": beh_verdict, "response": resp_verdict,
            "multi_seed": "stable" if beh_stable else "unstable",
            "verdict": final}


def run():
    af = fa.load_all()
    print("episode counts:", {p: len(af[p]) for p in PROFILES})
    fa.run(af)
    # difference matrix
    matrix_path = os.path.join(ANALYSIS, "POLICY_DIFFERENCE_MATRIX_V2.csv")
    pairs = list(itertools.combinations(PROFILES, 2))
    pair_verdicts = {}
    with open(matrix_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["policy_a", "policy_b", "artifact_distinct", "semantic_distinct",
                    "behavior_distance", "response_distance", "top_feature_effect",
                    "multi_seed_stable", "multi_scenario_status", "verdict"])
        for pa, pb in pairs:
            art = True  # sealed artifact bundles are unique across B0..B3
            pv = verdict_for((pa, pb), af)
            pair_verdicts[(pa, pb)] = pv
            top = pv["behavioral_top"][0] if pv["behavioral_top"] else {}
            w.writerow([pa, pb, "distinct" if art else "same", "distinct", pv.get("behavior_distance"),
                        pv.get("response_distance"),
                        f"{top.get('feature','')} d={top.get('cohens_d','')}"
                        if top else "none",
                        pv.get("multi_seed"), "NOT_YET", pv.get("verdict")])
    print("matrix written", matrix_path)
    # write fingerprints + DB
    repo = get_policy_repository()
    for prof in PROFILES:
        if len(af[prof]) < 10:
            print("WARN: insufficient", prof, len(af[prof]))
            continue
        agg = fp2.aggregate_fingerprint(prof, af[prof])
        payload = {**agg, "fingerprint_version": "fp-v2"}
        out = os.path.join(FPDIR, f"{PROFILE_TO_PID[prof]}_fp-v2.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        fp_obj = EmpiricalFingerprint(
            policy_id=PROFILE_TO_PID[prof],
            fingerprint_version="fp-v2",
            scenario_set=["S2"],
            seed_set=list(SEEDS),
            episode_count=len(af[prof]),
            behavior_features=payload["behavioral"],
            response_signature=payload["response"],
            feature_availability=payload["availability"],
            source_logs_hash="common_calibration_dev_7001-7010",
            schema_version="fp-v2")
        repo.add_fingerprint(fp_obj)
        print("fingerprint stored", PROFILE_TO_PID[prof])
    # pair validation records
    for pa, pb in pairs:
        pv = pair_verdicts[(pa, pb)]
        pid_a, pid_b = PROFILE_TO_PID[pa], PROFILE_TO_PID[pb]
        top = pv["behavioral_top"]
        resp_top = [x for x in fa.pair_analysis(pa, pb, af)["response"][:3]]
        ev = {"fingerprint_version": "fp-v2", "scenario": "S2",
              "seed_set": list(SEEDS), "n": [pv.get("na"), pv.get("nb")],
              "behavioral": {"behavior_distance": pv.get("behavior_distance"),
                             "top_feature_effects": [
                                 {"feature": x["feature"], "mean_a": x["mean_a"],
                                  "mean_b": x["mean_b"], "cohens_d": x["cohens_d"],
                                  "direction_consistency": x["direction_consistency"]}
                                 for x in top[:5]]},
              "response": {"response_distance": pv.get("response_distance"),
                           "top_effects": [
                               {"feature": x["feature"], "mean_a": x["mean_a"],
                                "mean_b": x["mean_b"], "cohens_d": x["cohens_d"]}
                               for x in resp_top]},
              "multi_seed": {"status": pv.get("multi_seed"),
                             "stability_basis": "direction_consistency>=0.8 on top effects"},
              "note": "B0-B3 common calibration; only B3 has runtime adaptive events; "
                      "spatial metrics are White-radar-visible proxies"}
        v = ValidationRecord(candidate_policy_id=pid_a, reference_policy_id=pid_b,
                             artifact_same=False,
                             semantic_difference={"declared": "distinct profiles"},
                             empirical_distance=pv.get("behavior_distance"),
                             feature_differences=[x["feature"] for x in top[:5]],
                             multi_seed_stable=(pv.get("multi_seed") == "stable"),
                             multi_scenario_stable=False,
                             novelty_verdict=pv.get("verdict"),
                             evaluation_role="general_opponent",
                             evidence=ev)
        repo.add_validation(v)
        print("validation stored", pid_a, "vs", pid_b, "->", pv.get("verdict"))
    json.dump({f"{a} vs {b}": pair_verdicts[(a, b)] for a, b in pairs},
              open(os.path.join(ANALYSIS, "PAIR_VERDICTS_V2.json"), "w"),
              indent=2, ensure_ascii=False)
    return af, pair_verdicts


if __name__ == "__main__":
    run()
