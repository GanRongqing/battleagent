#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""auto_register.py — store candidate fp-v2 fingerprint + pair validation records
and write AUTO_POLICY_FP_V2.json / AUTO_POLICY_NOVELTY_REPORT.md.

Run after auto_evolution_analysis produced the S2 results.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "strategy_library"))
import strategy_library.policy_fp2 as fp2  # noqa: E402
import strategy_library.fp2_analysis as fa  # noqa: E402
import auto_evolution_analysis as aea  # noqa: E402
from strategy_library.policy_models import EmpiricalFingerprint, ValidationRecord  # noqa: E402
from strategy_library.policy_repository import get_policy_repository  # noqa: E402

OUT = os.path.join(ROOT, "policy_system", "evolution", "auto_0001")
CAL = os.path.join(OUT, "calibration_s2")
CAND = "black-auto-0001-v1"
P = {"B0_RANDOM": "black-b0-v1", "B1_MULTI_AXIS": "black-b1-v1",
     "B2_COORDINATED_PRESSURE": "black-b2-v1", "B3_ADAPTIVE": "black-b3-v1"}


def main():
    af, res, near, ev = aea.run(CAL)
    summary = aea.write_outputs(CAL, res, near, ev)
    # aggregate candidate fp-v2 (behavioral includes injected structure group)
    agg = fp2.aggregate_fingerprint("AUTO_FEINT_SWITCH", af["AUTO_FEINT_SWITCH"])
    payload = {**agg, "fingerprint_version": "fp-v2",
               "policy_id": CAND,
               "empirical_behavior_class": "phased_feint_switch_pressure"}
    json.dump(payload, open(os.path.join(OUT, "AUTO_POLICY_FP_V2.json"), "w"),
              indent=2, ensure_ascii=False)
    repo = get_policy_repository()
    fp_obj = EmpiricalFingerprint(
        policy_id=CAND, fingerprint_version="fp-v2", scenario_set=["S2"],
        seed_set=list(range(7001, 7011)), episode_count=len(af["AUTO_FEINT_SWITCH"]),
        behavior_features=payload["behavioral"], response_signature=payload["response"],
        feature_availability=payload["availability"],
        source_logs_hash="auto_0001_s2_7001-7010", schema_version="fp-v2")
    repo.add_fingerprint(fp_obj)
    for ref, v in res.items():
        evd = {"fingerprint_version": "fp-v2", "scenario": "S2",
               "seed_set": list(range(7001, 7011)), "n": [v.get("na"), v.get("nb")],
               "behavioral": {"behavior_distance": v.get("behavior_distance"),
                              "top_feature_effects": [
                                  {"feature": x["feature"], "mean_a": x["mean_a"],
                                   "mean_b": x["mean_b"], "cohens_d": x["cohens_d"],
                                   "direction_consistency": x["direction_consistency"]}
                                  for x in v["behavioral_top"][:5]]},
               "response": {"response_distance": v.get("response_distance"),
                            "top_effects": v.get("response_top", [])},
               "multi_seed": {"status": v.get("multi_seed")},
               "note": "auto candidate common calibration; fp-v3 structural features included"}
        rec = ValidationRecord(candidate_policy_id=CAND, reference_policy_id=P[ref],
                               artifact_same=False,
                               semantic_difference={"declared": "feint_and_switch vs ref"},
                               empirical_distance=v.get("behavior_distance"),
                               feature_differences=[x["feature"] for x in v["behavioral_top"][:5]],
                               multi_seed_stable=(v.get("multi_seed") == "stable"),
                               multi_scenario_stable=False,
                               novelty_verdict=v.get("verdict"),
                               evaluation_role="stress_test", evidence=evd)
        repo.add_validation(rec)
    # novelty report
    lines = ["# AUTO_POLICY_NOVELTY_REPORT — black-auto-0001-v1 vs B0-B3 (S2, 7001-7010)", "",
             f"nearest existing policy = {near[0] if near else None} (behavior distance {near[1] if near else None})", "",
             "| reference | behavior distance | response distance | top feature | Cohen's d | seed consistency | verdict |",
             "|---|---|---|---|---|---|---|"]
    for ref, v in res.items():
        t = v["behavioral_top"][0] if v["behavioral_top"] else {}
        lines.append(f"| {ref} | {v.get('behavior_distance')} | {v.get('response_distance')} | "
                     f"{t.get('feature','')} | {t.get('cohens_d','')} | "
                     f"{t.get('direction_consistency','')} | {v.get('verdict')} |")
    lines += ["", "Generic fp-v3 structural features (uniform for all policies):",
              "reserve_fraction, early/late commitment ratios, role_asymmetry_index, "
              "dominant_axis_shift_count, phase_switch_count, continuous_replan_count."]
    open(os.path.join(OUT, "AUTO_POLICY_NOVELTY_REPORT.md"), "w").write("\n".join(lines))
    print(json.dumps({"nearest": near, "verdicts": {P[k]: v["verdict"] for k, v in res.items()}},
                     indent=2))
    return af, res, near


if __name__ == "__main__":
    main()
