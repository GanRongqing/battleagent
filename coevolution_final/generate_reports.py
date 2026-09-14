#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""coevolution_final/generate_reports.py — markdown tables + final reports.

Requires analyze.py to have run (stage_aggregate.csv, stage_paired_deltas.csv,
w6_mechanism_stats.csv, table CSVs). Produces table1/table2/table3 markdown, the
THREE_STAGE_FINAL_REPORT.md, COEVOLUTION_FINAL_SUMMARY.md, and prints the terminal summary.
"""
import csv
import json
import os
import sys

OUT = os.path.dirname(os.path.abspath(__file__))
TAB = os.path.join(OUT, "tables")
REP = os.path.join(OUT, "reports")
os.makedirs(REP, exist_ok=True)

SCALES = ["S1", "S2", "S3"]
STAGE_LABEL = {"Stage0": "Stage 0 Initial (W5×B0)",
               "Stage1": "Stage 1 Black Evolved (W5×B3)",
               "Stage2": "Stage 2 White Adapted (W6×B3)"}


def read(path):
    return list(csv.DictReader(open(path)))


def md_table(headers, rows):
    out = []
    sep = "| " + " | ".join(["---"] * len(headers)) + " |"
    out.append("| " + " | ".join(headers) + " |")
    out.append(sep)
    for r in rows:
        out.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(out)


def main():
    agg = read(os.path.join(OUT, "stage_aggregate.csv"))
    pair = read(os.path.join(OUT, "stage_paired_deltas.csv"))
    mech = read(os.path.join(OUT, "w6_mechanism_stats.csv"))
    t1 = read(os.path.join(TAB, "table1_three_stage.csv"))
    man = json.load(open(os.path.join(OUT, "config_manifest.json")))
    A = {(r["scenario"], r["stage"]): r for r in agg}

    # ── table1 md ──
    hdr = ["Scale", "Metric", "Stage 0\nInitial W5×B0", "Stage 1\nBlack Evolved W5×B3",
           "Stage 2\nWhite Adapted W6×B3", "Δ Black Evolution\n(S1 − S0)",
           "Δ White Adaptation\n(S2 − S1)"]
    rows = [[r["Scale"], r["Metric"], r["Stage0 Initial W5xB0"], r["Stage1 Black Evolved W5xB3"],
             r["Stage2 White Adapted W6xB3"], r["Delta Black Evolution (S1-S0)"],
             r["Delta White Adaptation (S2-S1)"]] for r in t1]
    open(os.path.join(TAB, "table1_three_stage.md"), "w", encoding="utf-8").write(
        "# TABLE 1 — Three-Stage Co-Evolution Evaluation\n\n"
        "N = 10 per (scale × stage), paired holdout seeds 4001–4010.\n\n"
        + md_table(hdr, rows) + "\n")

    # ── table2 md (rebuilt from w6_mechanism_stats, Stage2 only) ──
    keep = ["unique_intercept_plan_changes", "unsafe_close_entries",
            "handoff_count", "successful_handoff_count",
            "track_maintenance_assignments", "unique_screen_reconfigurations",
            "screen_assignments", "unique_high_risk_transitions",
            "critical_risk_entries", "late_intercept_events"]
    mech_name = {"unique_intercept_plan_changes": "Unique Intercept Plan Changes",
                 "unsafe_close_entries": "Unsafe-Close Entries",
                 "handoff_count": "Handoffs",
                 "successful_handoff_count": "Successful Handoffs",
                 "track_maintenance_assignments": "Track-Maintenance Assignments",
                 "unique_screen_reconfigurations": "Screen Reconfigurations",
                 "screen_assignments": "Screen Deployments",
                 "unique_high_risk_transitions": "High-Risk Transitions",
                 "critical_risk_entries": "Critical-Risk Entries",
                 "late_intercept_events": "Late-Intercept Events"}
    rows2 = []
    for sc in SCALES:
        for c in keep:
            v = [r for r in mech if r["scenario"] == sc and r["metric"] == c]
            rows2.append([sc, mech_name.get(c, c)] + v[0]["Stage2"] if v else [sc, c, "0"])
    hdr2 = ["Scale", "Mechanism", "Stage 2 mean/episode (W6×B3)"]
    open(os.path.join(TAB, "table2_w6_mechanisms.md"), "w", encoding="utf-8").write(
        "# TABLE 2 — W6 Anti-Evasion Mechanism Statistics (Stage 2 only)\n\n"
        + md_table(hdr2, rows2) + "\n")

    # ── table3 md ──
    t3 = """# TABLE 3 — Evolution Stages and Mechanisms

| Stage | White | Black | Main capability |
|---|---|---|---|
| Stage 0 — Initial | W5 (frozen) | B0_RANDOM | baseline Harness + random opponent |
| Stage 1 — Black Evolved | W5 (frozen) | B3_ADAPTIVE | Black enhancement: legal-observation-driven replanning, lane shift, dispersion, adaptive penetration |
| Stage 2 — White Adapted | W6 | B3 (frozen) | White enhancement: predictive interception (standoff), pursuit-cost-aware allocation, target handoff, UAV track maintenance, adaptive defensive screen, breakthrough-horizon risk |

Notes: both sides evolve under the fair-play observation boundary; no physics buff; feature-gated
mechanisms allow ablation; every release is hash-versioned (see `config_manifest.json`).
"""
    open(os.path.join(TAB, "table3_evolution_stages.md"), "w", encoding="utf-8").write(t3)

    # ── THREE_STAGE_FINAL_REPORT.md ──
    rep = ["# THREE-STAGE CO-EVOLUTION FINAL REPORT", "",
           "## Setup", "",
           "- Stages: Stage0 W5×B0 (initial), Stage1 W5×B3 (black evolved), Stage2 W6×B3 "
           "(white adapted).",
           "- Scales S1 5+5v10 / S2 10+10v20 / S3 15+15v30; holdout seeds 4001–4010; N=10 "
           "per (scale×stage); paired by seed.",
           "- Frozen hashes recorded in `coevolution_final/config_manifest.json` "
           "(W5 legacy `a7842b29…` / runtime file, Skill `155b0201…`, B3, W6, physics "
           "`engine.py:58aab5ad… tzb_engine.py:396ba7a3…`).",
           "- Reproducibility control: per-game RNG reseed in `scenario_builder.py` "
           "(determinism fix, not a physics/balance change).",
           "- Total main episodes: 90 (hard cap respected).", "",
           "## Results", ""]
    for sc in SCALES:
        rep.append(f"### {sc}  (White {A[(sc,'Stage0')]['friendly_usv_initial']}+"
                   f"{A[(sc,'Stage0')]['friendly_uav_initial']} vs Black "
                   f"{A[(sc,'Stage0')]['enemy_combat_usv_initial']})")
        rep.append("")
        hd = ["metric", "Stage0", "Stage1", "Stage2", "Δ black (S1−S0)", "Δ white (S2−S1)"]
        rr = []
        for m, label in [("clean_rate", "clean win rate"), ("enemy_combat_kills", "enemy kills"),
                         ("friendly_usv_dead", "friendly usv loss"),
                         ("breakthrough_rate", "breakthrough rate"),
                         ("explored_area_km2", "explored km²"), ("resolution_time_s", "resolution s")]:
            f0 = float(A[(sc, "Stage0")][m]); f1 = float(A[(sc, "Stage1")][m]); f2 = float(A[(sc, "Stage2")][m])
            d1 = f1 - f0; d2 = f2 - f1
            rr.append([label, f"{f0:.3f}" if m.endswith("rate") else f"{f0:.1f}",
                       f"{f1:.3f}" if m.endswith("rate") else f"{f1:.1f}",
                       f"{f2:.3f}" if m.endswith("rate") else f"{f2:.1f}",
                       f"{d1:+.3f}" if m.endswith("rate") else f"{d1:+.1f}",
                       f"{d2:+.3f}" if m.endswith("rate") else f"{d2:+.1f}"])
        rep.append(md_table(hd, rr) + "\n")
    rep.append("## Paired deltas (mean over 10 paired seeds) + bootstrap 95% CI\n")
    rep.append(md_table(["scale", "metric", "Δ black mean", "Δ white mean",
                         "boot95CI black (utility)", "boot95CI white (utility)"],
                        [[r["scenario"], r["metric_name"], r["mean_delta_black(S1-S0)"],
                          r["mean_delta_white(S2-S1)"], r["boot95CI_black_on_utility"],
                          r["boot95CI_white_on_utility"]] for r in pair]) + "\n")
    rep.append("## Recovery interpretation\n")
    rep.append("For each continuous metric, utility = ±value so that higher = better; "
               "recovery_ratio = (S2−S1)/(S0−S1) on the utility scale (0 = no recovery, "
               "1 = full recovery to Stage 0, >1 = above baseline, <0 = further degradation). "
               "Because N=10, recovery is reported descriptively and not as a significance claim.\n")
    rep.append("## Honest scope\n")
    rep.append("No self-play convergence, Nash equilibrium, or automatic strategy discovery is "
               "claimed. The report is a descriptive, seed-paired, mechanism-audited comparison of "
               "two one-sided evolution steps.")
    open(os.path.join(REP, "THREE_STAGE_FINAL_REPORT.md"), "w", encoding="utf-8").write("\n".join(rep) + "\n")

    # ── COEVOLUTION_FINAL_SUMMARY.md ──
    summary = ["# CO-EVOLUTION FINAL SUMMARY", "",
               "## What was produced",
               "1. Frozen versions: W5 (legacy `a7842b29…`; runtime file behaviourally identical), "
               "Skill v1 (`155b0201…`), B3, W6-FINAL-CANDIDATE (`agent_hybrid_w6.py` + "
               "`anti_evasion/`), physics unchanged.",
               "2. Three-stage paired FINAL experiment: 3 scales × 3 stages × 10 holdout seeds "
               "(4001–4010) = 90 episodes (hard cap).",
               "3. Mechanism fire-check + ablation for W6 (Stage 2 only).",
               "4. Systematic framework: Evidence-Driven Alternating Adversarial Co-Evolution "
               "(`COEVOLUTION_FRAMEWORK_METHOD.md` + framework / instance figures).",
               "5. Tables 1–3, five three-stage figures, aggregate/paired/mechanism CSVs.",
               "", "## Key artifacts",
               "- `coevolution_final/config_manifest.json`",
               "- `final_episode_results.csv`, `stage_aggregate.csv`, `stage_paired_deltas.csv`, "
               "`w6_mechanism_stats.csv`, `optional_w6_b0_regression.csv`",
               "- `tables/table1..3`, `figures/*`, `reports/*`", "",
               "## Honest limitations",
               "- N=10/setting; paired descriptive statistics with offline bootstrap CIs; no "
               "significance inflation.",
               "- Residual W6 weakness on some seeds is documented (see `config_manifest.json` "
               "DEV gate notes).",
               ]
    open(os.path.join(REP, "COEVOLUTION_FINAL_SUMMARY.md"), "w", encoding="utf-8").write(
        "\n".join(summary) + "\n")

    print("reports + tables md written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
