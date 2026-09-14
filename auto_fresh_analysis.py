#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""auto_fresh_analysis.py — fresh-seed validation (7101-7110) candidate vs nearest ref.

Also reports DEV (7001-7010) vs FRESH (7101-7110) direction consistency for the
top structural/behavioral differences.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "strategy_library"))
sys.path.insert(0, os.path.join(ROOT, "hsystem"))
import auto_evolution_analysis as aea  # noqa: E402

OUT = os.path.join(ROOT, "policy_system", "evolution", "auto_0001")


def build(ref_profile, ref_dir, seeds):
    cfps, cev = aea.load_candidate(os.path.join(OUT, "fresh_candidate"), seeds)
    rfps, rev = aea.load_candidate(os.path.join(OUT, ref_dir), seeds, profile=ref_profile)
    all_fps = {ref_profile: rfps, "AUTO_FEINT_SWITCH": cfps}
    aea.inject_structure(all_fps, "S2", candidate="AUTO_FEINT_SWITCH", candidate_events=cev)
    return all_fps, cev


def main():
    seeds = list(range(7101, 7111))
    all_fps, cev = build("B0_RANDOM", "fresh_b0", seeds)
    v = aea.pair_verdict("AUTO_FEINT_SWITCH", "B0_RANDOM", all_fps)
    lines = ["# AUTO_POLICY_FRESH_SEED_VALIDATION — black-auto-0001-v1 vs B0 (nearest)",
             "", "Seeds 7101-7110 (fresh DEV, disjoint from 7001-7010).",
             f"- candidate N = {v.get('na')}, reference N = {v.get('nb')}",
             f"- behavior distance = {v.get('behavior_distance')}",
             f"- response distance = {v.get('response_distance')}",
             f"- multi-seed = {v.get('multi_seed')}",
             f"- fresh novelty verdict = {v.get('verdict')}", "",
             "## Top behavioral differences (fresh seeds)", "",
             "| feature | mean cand | mean ref | Cohen's d | seed consistency |",
             "|---|---|---|---|---|"]
    for x in v["behavioral_top"]:
        lines.append(f"| {x['feature']} | {x['mean_a']} | {x['mean_b']} | {x['cohens_d']} | "
                     f"{x['direction_consistency']} |")
    # DEV vs FRESH direction comparison for key features
    dev_all = aea.run(os.path.join(OUT, "calibration_s2"), scenario="S2",
                      seeds=list(range(7001, 7011)))[0]
    dev_v = aea.pair_verdict("AUTO_FEINT_SWITCH", "B0_RANDOM", dev_all)
    lines += ["", "## DEV (7001-7010) vs FRESH (7101-7110)", "",
              "| feature | DEV d | FRESH d | direction preserved |",
              "|---|---|---|---|"]
    dev_map = {x["feature"]: x for x in dev_v["behavioral_top"]}
    for x in v["behavioral_top"]:
        d = dev_map.get(x["feature"], {})
        same = (d.get("cohens_d") is not None and x.get("cohens_d") is not None and
                (d["cohens_d"] > 0) == (x["cohens_d"] > 0))
        lines.append(f"| {x['feature']} | {d.get('cohens_d','')} | {x['cohens_d']} | {same} |")
    open(os.path.join(OUT, "AUTO_POLICY_FRESH_SEED_VALIDATION.md"), "w").write("\n".join(lines))
    json.dump({"fresh": v, "dev": dev_v}, open(os.path.join(OUT, "AUTO_POLICY_FRESH.json"), "w"),
              indent=2, default=str)
    print("fresh verdict:", v.get("verdict"), "dist", v.get("behavior_distance"))
    for x in v["behavioral_top"][:3]:
        print(" ", x["feature"], x["cohens_d"], x["direction_consistency"])


if __name__ == "__main__":
    main()
