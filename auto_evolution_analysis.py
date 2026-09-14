#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""auto_evolution_analysis.py — novelty analysis for the auto candidate.

Builds candidate fp-v2 from its EPISODES.csv + traces, augments ALL policies with
generic fp-v3 structural features (plan-derived, uniform), then compares the
candidate to each reference policy (B0-B3) using the same paired/seed-stable logic.
"""
import csv
import importlib.util
import itertools
import json
import math
import os
import statistics
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "strategy_library"))
sys.path.insert(0, os.path.join(ROOT, "hsystem"))
import strategy_library.policy_fp2 as fp2  # noqa: E402
import strategy_library.policy_fp3 as fp3  # noqa: E402
import strategy_library.fp2_analysis as fa  # noqa: E402
import opponent_profiles as op  # noqa: E402
import opponent_auto_profiles as auto  # noqa: E402

SCENARIO_N = {"S1": 10, "S2": 20, "S3": 30}
REF_PROFILES = ["B0_RANDOM", "B1_MULTI_AXIS", "B2_COORDINATED_PRESSURE", "B3_ADAPTIVE"]
P = {"B0_RANDOM": "B0", "B1_MULTI_AXIS": "B1", "B2_COORDINATED_PRESSURE": "B2",
     "B3_ADAPTIVE": "B3", "AUTO_FEINT_SWITCH": "AUTO1"}

_sb = None


def _scenario_builder():
    global _sb
    if _sb is None:
        spec = importlib.util.spec_from_file_location(
            "scenario_builder", os.path.join(ROOT, "hsystem", "sim_script",
                                             "20250819TZB", "scenario_builder.py"))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        _sb = m
    return _sb


def plans_for(profile, seed, scenario):
    n = SCENARIO_N[scenario]
    ys = _scenario_builder()._deploy_ys(n, "fixed_frontage")
    if profile == "B0_RANDOM":
        return _scenario_builder()._random_waypoint_paths(seed, ys)
    if profile == "AUTO_FEINT_SWITCH":
        p, _ = auto.generate_initial_paths_auto(seed, ys, n_groups=max(1, (n + 3) // 4))
        return p
    return op.generate_initial_paths(profile, seed, ys)


def structure_for(profile, seed, scenario, events=None):
    return fp3.with_events(fp3.plan_features(plans_for(profile, seed, scenario)), events)


def inject_structure(all_fps, scenario, candidate=None, candidate_events=None):
    for prof, fps in all_fps.items():
        for f in fps:
            ev = None
            if candidate and prof == candidate:
                ev = (candidate_events or {}).get(f["seed"])
            f["behavioral"]["structure"] = {
                k: {"value": v, "availability": "available"}
                for k, v in structure_for(prof, f["seed"], scenario, ev).items()}
            # uniform continuous-replan feature: B3 from its event counter, candidate
            # from its phase-event sidecar, B0-B2 true zero (no runtime replanning).
            rep = 0
            if prof == "B3_ADAPTIVE":
                rep = (f["behavioral"].get("adaptation", {})
                       .get("adaptive_replan_count", {}).get("value") or 0)
            elif candidate and prof == candidate:
                rep = (ev or {}).get("replan_count", 0) or 0
            f["behavioral"]["structure"]["continuous_replan_count"] = {
                "value": rep, "availability": "available"}


def load_candidate(out_dir, seeds, scenario="S2", profile="AUTO_FEINT_SWITCH"):
    ep = {}
    p = os.path.join(out_dir, "EPISODES.csv")
    if not os.path.exists(p):
        return [], {}
    for r in csv.DictReader(open(p)):
        if int(r["seed"]) in seeds:
            ep[int(r["seed"])] = r
    events = {}
    fps = []
    for sd in seeds:
        if sd not in ep:
            continue
        row = ep[sd]
        if row.get("http_or_trace_errors") not in (None, "", "0", 0):
            continue
        evp = os.path.join(out_dir, "traces", f"s{sd}_autoevents.json")
        if os.path.exists(evp):
            try:
                events[sd] = json.load(open(evp))
            except Exception:
                pass
        traces_dir = os.path.join(out_dir, "traces")
        old = fp2.TRACES
        fp2.TRACES = traces_dir
        fps.append(fp2.episode_fp(profile, sd, row, fp2.load_trace(profile, sd)))
        fp2.TRACES = old
    return fps, events


def pair_verdict(pa, pb, all_fps, n_min=10):
    na, nb = len(all_fps[pa]), len(all_fps[pb])
    if min(na, nb) < n_min:
        return {"verdict": "INSUFFICIENT_EVIDENCE", "behavioral_top": [],
                "behavior_distance": None, "response_distance": None,
                "multi_seed": "insufficient", "na": na, "nb": nb}
    pr = fa.pair_analysis(pa, pb, all_fps)
    gd = fa.global_dist(pa, pb, all_fps)
    beh, resp = pr["behavioral"], pr["response"]
    # drop degenerate effects (zero pooled variance -> unbounded Cohen's d)
    sane = [x for x in beh if x.get("cohens_d") is not None and abs(x["cohens_d"]) < 1000.0]
    strong = [x for x in sane if x["direction_consistency"] is not None
              and x["direction_consistency"] >= 0.8 and abs(x["cohens_d"]) >= 1.0]
    bd = gd.get("behavioral_distance")
    beh_stable = bool(strong) and (bd is not None and bd > 0.3)
    resp_distinct = gd.get("response_distance") is not None and gd["response_distance"] > 0.3
    if not beh:
        verdict = "INSUFFICIENT_EVIDENCE"
    elif beh_stable:
        verdict = "EMPIRICALLY_DISTINCT"
    else:
        verdict = "INCONCLUSIVE"
    return {"na": na, "nb": nb, "behavioral_top": strong[:5] if strong else sane[:5],
            "all_behavioral": sane[:10], "response_top": resp[:5],
            "behavior_distance": bd, "response_distance": gd.get("response_distance"),
            "response_distinct": resp_distinct,
            "multi_seed": "stable" if beh_stable else "unstable", "verdict": verdict}


def run(out_dir, scenario="S2", seeds=None, candidate="AUTO_FEINT_SWITCH",
        write_reports=True, ref_fps=None):
    seeds = seeds or list(range(7001, 7011))
    all_fps = {k: list(v) for k, v in (ref_fps or fa.load_all()).items()}
    cfps, cevents = load_candidate(out_dir, seeds, scenario, candidate)
    all_fps[candidate] = cfps
    inject_structure(all_fps, scenario, candidate=candidate, candidate_events=cevents)
    results = {}
    for ref in REF_PROFILES:
        results[ref] = pair_verdict(candidate, ref, all_fps)
    nearest = None
    for ref, v in results.items():
        bd = v.get("behavior_distance")
        if bd is not None and (nearest is None or bd < nearest[1]):
            nearest = (ref, bd)
    return all_fps, results, nearest, cevents


def write_outputs(out_dir, results, nearest, cevents, scenario="S2", seeds=None):
    seeds = seeds or list(range(7001, 7011))
    rows = []
    for ref, v in results.items():
        top = v["behavioral_top"][0] if v["behavioral_top"] else {}
        rows.append({"candidate": "AUTO1", "reference": P[ref],
                     "behavior_distance": v.get("behavior_distance"),
                     "response_distance": v.get("response_distance"),
                     "top_feature": top.get("feature", ""),
                     "top_effect_d": top.get("cohens_d", ""),
                     "top_seed_consistency": top.get("direction_consistency", ""),
                     "multi_seed": v.get("multi_seed"), "verdict": v.get("verdict")})
    with open(os.path.join(out_dir, "AUTO_POLICY_PAIRWISE.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    summary = {"scenario": scenario, "seeds": seeds,
               "nearest_neighbor": nearest[0] if nearest else None,
               "nearest_distance": nearest[1] if nearest else None,
               "results": results, "events": cevents}
    with open(os.path.join(out_dir, "AUTO_POLICY_NOVELTY.json"), "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
    return summary


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "policy_system/evolution/auto_0001/calibration_s2"
    af, res, near, ev = run(out)
    for ref, v in res.items():
        print(P[ref], v["verdict"], "dist", v.get("behavior_distance"),
              "top", (v["behavioral_top"][0] if v["behavioral_top"] else None))
    print("nearest:", near)
