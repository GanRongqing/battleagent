#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""auto_cross_analysis.py — multi-scenario validation (S1/S3) candidate vs nearest (B0)."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "strategy_library"))
sys.path.insert(0, os.path.join(ROOT, "hsystem"))
import auto_evolution_analysis as aea  # noqa: E402

OUT = os.path.join(ROOT, "policy_system", "evolution", "auto_0001")


def build(scenario, seeds):
    cd, bd = f"cross_{scenario}_candidate", f"cross_{scenario}_b0"
    cfps, cev = aea.load_candidate(os.path.join(OUT, cd), seeds)
    rfps, _ = aea.load_candidate(os.path.join(OUT, bd), seeds, profile="B0_RANDOM")
    all_fps = {"B0_RANDOM": rfps, "AUTO_FEINT_SWITCH": cfps}
    aea.inject_structure(all_fps, scenario, candidate="AUTO_FEINT_SWITCH", candidate_events=cev)
    return all_fps


def main():
    seeds = list(range(7201, 7206))
    lines = ["# AUTO_POLICY_MULTI_SCENARIO_VALIDATION — black-auto-0001-v1 vs B0", "",
             "Candidate and reference B0 both run on fresh DEV seeds 7201-7205.",
             "S1 = White 5+5 vs Black 10; S3 = White 15+15 vs Black 30.", ""]
    summary = {}
    for scenario in ("S1", "S3"):
        all_fps = build(scenario, seeds)
        v = aea.pair_verdict("AUTO_FEINT_SWITCH", "B0_RANDOM", all_fps, n_min=5)
        summary[scenario] = v
        lines += [f"## {scenario}", "",
                  f"- candidate N = {v.get('na')}, reference N = {v.get('nb')}",
                  f"- behavior distance = {v.get('behavior_distance')}",
                  f"- verdict = {v.get('verdict')}", "",
                  "| feature | mean cand | mean ref | Cohen's d | seed consistency |",
                  "|---|---|---|---|---|"]
        for x in v["behavioral_top"][:6]:
            lines.append(f"| {x['feature']} | {x['mean_a']} | {x['mean_b']} | {x['cohens_d']} | "
                         f"{x['direction_consistency']} |")
        lines.append("")
    core = ["structure.reserve_fraction", "structure.role_asymmetry_index",
            "structure.dominant_axis_shift_count", "structure.phase_switch_count",
            "structure.continuous_replan_count"]
    preserved = {}
    for scenario in ("S1", "S3"):
        feats = {x["feature"]: x for x in summary[scenario]["behavioral_top"]}
        preserved[scenario] = {c: (feats.get(c, {}).get("direction_consistency")) for c in core}
    lines += ["## Core signature preservation (direction consistency by scenario)", "",
              "| core feature | S1 | S3 |", "|---|---|---|"]
    for c in core:
        lines.append(f"| {c} | {preserved['S1'].get(c)} | {preserved['S3'].get(c)} |")
    multi = all(summary[s].get("verdict") == "EMPIRICALLY_DISTINCT" for s in ("S1", "S3"))
    lines += ["", f"multi_scenario_validated = {'YES' if multi else 'PARTIAL'}", ""]
    open(os.path.join(OUT, "AUTO_POLICY_MULTI_SCENARIO_VALIDATION.md"), "w").write("\n".join(lines))
    json.dump(summary, open(os.path.join(OUT, "AUTO_POLICY_MULTI_SCENARIO.json"), "w"),
              indent=2, default=str)
    for s in ("S1", "S3"):
        print(s, summary[s].get("verdict"), "dist", summary[s].get("behavior_distance"))
    print("multi_scenario_validated =", "YES" if multi else "PARTIAL")


if __name__ == "__main__":
    main()
