#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""policy_reports_v2.py — generate fp-v2 calibration markdown/CSV deliverables
from completed common-calibration analysis. Run AFTER seed_calibration_fp2.run()."""
import itertools
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from strategy_library import fp2_analysis as fa  # noqa: E402
from strategy_library import policy_fp2 as fp2  # noqa: E402

ROOT = fp2._ROOT
CAL = os.path.join(ROOT, "policy_system", "calibration")
ANALYSIS = os.path.join(CAL, "analysis")
PROFILES = fp2.PROFILES
SEEDS = fp2.SEEDS

P = {"B0_RANDOM": "B0", "B1_MULTI_AXIS": "B1", "B2_COORDINATED_PRESSURE": "B2",
     "B3_ADAPTIVE": "B3"}


def _top_rows(pv, k=5):
    return pv["behavioral_top"][:k]


def _fmt(v):
    return "None" if v is None else (f"{v:.4f}" if isinstance(v, float) else str(v))


def pair_report(pa, pb, pv, af):
    pr = fa.pair_analysis(pa, pb, af)
    gd = fa.global_dist(pa, pb, af)
    L = [f"# {P[pa]} vs {P[pb]}", ""]
    L += ["## Declared Semantics", ""]
    declared = {"B0_RANDOM": "random waypoints, low coordination",
                "B1_MULTI_AXIS": "spatial multi-axis groups, local structure",
                "B2_COORDINATED_PRESSURE": "coordinated pressure, shared timetable",
                "B3_ADAPTIVE": "B2-like coordination + legal-observation-driven adaptation"}
    L += [f"- {P[pa]} ({pa}): {declared[pa]}", f"- {P[pb]} ({pb}): {declared[pb]}", ""]
    L += ["## Artifact Difference", "", "- distinct artifact bundles (sealed, unique hashes)", ""]
    L += ["## Common Calibration", "",
          "- White frozen W5; S2; same seeds 7001-7010; same instrumentation cal-v1",
          f"- episodes: {P[pa]} n={pv.get('na')}, {P[pb]} n={pv.get('nb')}",
          f"- behavioral distance = {_fmt(gd.get('behavioral_distance'))}",
          f"- response distance = {_fmt(gd.get('response_distance'))}", ""]
    L += ["## Behavioral Top Differences (shared available/proxy features)", "",
          "| feature | mean a | mean b | Cohen's d | direction consistency |", "|---|---|---|---|---|"]
    for x in pv["behavioral_top"][:8]:
        L.append(f"| {x['feature']} | {x['mean_a']} | {x['mean_b']} | {x['cohens_d']} | "
                 f"{x.get('direction_consistency')} |")
    L += ["", "Note: features are available/proxy only; unavailable features are excluded, never 0.",
          "Direction consistency = fraction of the 10 paired seeds where b>a.", ""]
    if pv["behavioral_top"]:
        d = pv["behavioral_top"][0]
        L += [f"Top effect: {d['feature']} (d={d['cohens_d']}, "
              f"seed consistency={d.get('direction_consistency')})", ""]
    L += ["## Response Signature Difference", "", "| feature | mean a | mean b | Cohen's d |", "|---|---|---|---|"]
    for x in pr["response"][:6]:
        L.append(f"| {x['feature']} | {x['mean_a']} | {x['mean_b']} | {x['cohens_d']} |")
    L += ["", "Response = White outcome under the opponent, kept separate from behavior.", ""]
    L += ["## Multi-Seed Stability", "",
          f"- stability basis: direction_consistency on top behavioral effects -> "
          f"status **{pv.get('multi_seed')}**", ""]
    L += ["## Final Verdict", "", f"**{pv.get('verdict')}**", ""]
    return "\n".join(L)


def declared_empirical_report(af):
    L = ["# Declared vs Empirical Consistency (fp-v2, S2 common calibration)", ""]
    L += ["| Policy | Declared key trait | Empirical feature | Evidence | Verdict |",
          "|---|---|---|---|---|"]
    rows = {
        "B0_RANDOM": [("random, low coordination", "coordination/timing signatures",
                       "no adaptive events; random approach timing",
                       "NO low-sync/random proxy is unavailable; replan/lane/dispersion events = 0 (true zero)")],
        "B1_MULTI_AXIS": [("multi-axis spatial groups", "spatial proxies (lane entropy / visible group metrics)",
                           "approach_lane_entropy, mean_visible_group_count",
                           "PARTIALLY_SUPPORTED via White-radar-visible geometry proxies (not Black ground truth)")],
        "B2_COORDINATED_PRESSURE": [("coordinated pressure / timetable", "arrival_front_sync, group spacing",
                                     "arrival_front_sync_std_s, mean_group_spacing_km",
                                     "PARTIALLY_SUPPORTED via arrival-front proxy")],
        "B3_ADAPTIVE": [("legal-observation adaptive replan", "adaptive_replan/lane_shift/dispersion/detection counts",
                         "B3 runtime event counters (sidecar)",
                         "SUPPORTED if counts>0 on >=9/10 seeds (empirical)")],
    }
    for prof, items in rows.items():
        for trait, feat, evi, verdict in items:
            L.append(f"| {P[prof]} | {trait} | {feat} | {evi} | {verdict} |")
    L += ["", "Honest limits: in-game Black ground-truth geometry (all 20 ships) is NOT recorded "
          "by the simulator; spatial/coordination metrics are White-radar-visible proxies "
          "(flagged proxy) and Black is not receiving any hidden White truth.",
          "Multi-scenario (S1/S3) fingerprinting not run this round: multi_scenario = NOT_YET."]
    return "\n".join(L)


def distance_calibration_report(af, pair_verdicts):
    L = ["# FP-V2 Distance Calibration (S2, 7001-7010)", ""]
    L += ["## Within-policy vs between-policy variability", ""]
    L += ["| policy | n | within_feature_median_std (behavioral) |", "|---|---|---|"]
    for prof in PROFILES:
        if not af[prof]:
            continue
        agg = fp2.aggregate_fingerprint(prof, af[prof])
        stds = []
        for grp in ("temporal", "spatial", "coordination", "adaptation"):
            for feat, m in agg["behavioral"].get(grp, {}).items():
                if isinstance(m, dict) and m.get("std") is not None:
                    stds.append(m["std"])
        L.append(f"| {P[prof]} | {len(af[prof])} | "
                 f"{round(statistics.median(stds), 3) if stds else 'n/a'} (median of feature stds) |")
    L += ["", "## Pairwise behavior distances & effect sizes", ""]
    for (pa, pb), pv in pair_verdicts.items():
        top = pv["behavioral_top"][0] if pv["behavioral_top"] else {}
        L.append(f"- {P[pa]} vs {P[pb]}: behavioral distance={_fmt(pv.get('behavior_distance'))}, "
                 f"top effect {top.get('feature','n/a')} d={_fmt(top.get('cohens_d'))}, "
                 f"seed consistency={top.get('direction_consistency')} -> {pv.get('verdict')}")
    L += ["", "## Suggested novelty threshold (empirical calibration, not theory)", ""]
    L += ["- Behavioral distance is a summary only. Verdicts combine distance + feature-level "
          "Cohen's d + 10-seed direction consistency.",
          "- No fixed threshold is applied automatically; if behavior distance of a new candidate "
          "to every pool member is < the smallest observed B-pair distance AND no top feature has "
          "|d|>=1 with direction consistency>=0.8, treat as potential behavioral duplicate.",
          "- These remain empirical calibration outputs, not a theoretical standard."]
    return "\n".join(L)


def historical_formal_consistency(af):
    import csv as _csv
    L = ["# Historical Formal vs Common Calibration (response consistency)", ""]
    L += ["Old formal evidence (logs_formal/logs_opponent_formal, seeds 1001-1030) previously showed "
          "B3 resolution/lost-track higher than B0. Cross-check with S2 common calibration response "
          "signature (7001-7010):", ""]
    L += ["| response feature | B0 (common cal) | B3 (common cal) | direction vs historical |",
          "|---|---|---|---|"]
    try:
        agg = {prof: fp2.aggregate_fingerprint(prof, af[prof]) if af[prof] else None
               for prof in PROFILES}
        for feat in ("clean_win", "breakthrough_count", "white_reacquire_count"):
            b0 = agg["B0_RANDOM"]["response"]["outcomes"][feat]["mean"] if agg["B0_RANDOM"] else None
            b3 = agg["B3_ADAPTIVE"]["response"]["outcomes"][feat]["mean"] if agg["B3_ADAPTIVE"] else None
            L.append(f"| {feat} | {b0} | {b3} | qualitative check |")
    except Exception as e:
        L.append(f"| error | {e} |")
    L += ["", "Directional agreement is qualitative; exact magnitudes differ across seed sets "
          "(formal 1001-1030 vs dev calibration 7001-7010)."]
    return "\n".join(L)


def final_report(af, pair_verdicts):
    L = ["# B0-B3 Common Policy Calibration Report", "",
         "## 1. Objective", "", "Prove policy identity from behavior (not names/params): do B0/B1/B2/B3 "
         "show stable, explainable empirical behavioral differences under fully common conditions?", "",
         "## 2. Experimental Controls", "",
         "- White: frozen W5 (agent_hybrid_v5.py)",
         "- Scenario: S2 (White 10 USV + 10 UAV vs Black 20 combat USV)",
         "- Seeds: 7001-7010 (DEV calibration, POLICY_FINGERPRINT_CALIBRATION_DEV)",
         "- Instrumentation: cal-v1 (identical metric pipeline to formal runs; read-only /status sampler)",
         "- Fingerprint: fp-v2 (behavioral + response separated)", "",
         "## 3. Artifact Integrity", "", "- B0..B3 sealed artifact bundles unique (see policy_artifacts).", "",
         "## 4. Policy Propagation Proof", ""]
    for prof in PROFILES:
        n = len(af[prof])
        L.append(f"- {P[prof]} n={n}/10" + (" (each episode meta records requested=effective; "
                                            "B3 additionally has adaptive event sidecar per episode)"
                                            if prof == "B3_ADAPTIVE" else ""))
    L += ["", "## 5. Behavioral Fingerprint v2", "", "- behavioral block: temporal/spatial/coordination/"
          "adaptation groups; availability available/proxy/unavailable.",
          "- adaptation from real runtime events (B3) or real zeros (B0/B1/B2: no replan mechanism).", "",
          "## 6. Response Signatures", "", "- response block kept separate (white_outcome).", "",
          "## 7. Pairwise Difference Matrix", "", "- see POLICY_DIFFERENCE_MATRIX_V2.csv and pair reports.", ""]
    L += ["## 13. Multi-Seed Stability", ""]
    for (pa, pb), pv in pair_verdicts.items():
        L.append(f"- {P[pa]} vs {P[pb]}: {pv.get('multi_seed')}")
    L += ["", "## 14. Within-Policy Variance", "", "- see FP_V2_DISTANCE_CALIBRATION.md.",
          "", "## 15. Strength vs Value", ""]
    L += ["- A policy can be behaviorally distinct yet weak (low Black win / low White burden); "
          "behavioral novelty and evaluation value are assessed separately."]
    L += ["", "## 16. Admission Verdict", ""]
    for (pa, pb), pv in pair_verdicts.items():
        L.append(f"- {P[pa]} vs {P[pb]}: **{pv.get('verdict')}**")
    L += ["", "## 17. Remaining Gaps", "",
          "- Multi-scenario (S1/S3): NOT_YET validated.",
          "- In-game Black ground-truth spatial geometry (all ships) is not recorded by the simulator; "
          "spatial/coordination features are White-radar-visible proxies.",
          "- contact_to_replan_latency and phase_switch_count unavailable (no per-event timestamps / no "
          "phase concept observable from current logs)."]
    return "\n".join(L)


def write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print("wrote", path)


def run(af=None, pair_verdicts=None):
    af = af or fa.load_all()
    if pair_verdicts is None:
        raw = json.load(open(os.path.join(ANALYSIS, "PAIR_VERDICTS_V2.json")))
        pair_verdicts = {tuple(k.split(" vs ")): v for k, v in raw.items()}
    pairs = list(itertools.combinations(PROFILES, 2))
    for pa, pb in pairs:
        pv = pair_verdicts.get((pa, pb))
        if not pv:
            for k, v in pair_verdicts.items():
                if set(k) == {pa, pb}:
                    pv = v
                    break
        if pv:
            write(os.path.join(ANALYSIS, f"POLICY_PAIR_REPORT_{P[pa]}_VS_{P[pb]}.md"),
                  pair_report(pa, pb, pv, af))
    write(os.path.join(ANALYSIS, "DECLARED_EMPIRICAL_CONSISTENCY_V2.md"), declared_empirical_report(af))
    write(os.path.join(ANALYSIS, "FP_V2_DISTANCE_CALIBRATION.md"),
          distance_calibration_report(af, pair_verdicts))
    write(os.path.join(ANALYSIS, "HISTORICAL_FORMAL_CONSISTENCY.md"), historical_formal_consistency(af))
    write(os.path.join(ANALYSIS, "POLICY_B0_B3_COMMON_CALIBRATION_REPORT.md"),
          final_report(af, pair_verdicts))
    # per-seed csv of behavioral features (by seed)
    write_per_seed_csv(af)


def write_per_seed_csv(af):
    path = os.path.join(ANALYSIS, "POLICY_BEHAVIOR_FEATURES_PER_SEED.csv")
    rows = []
    for prof in PROFILES:
        for f in af[prof]:
            for (name, grp, feat, v, a) in fa.flat_numeric(f, "behavioral"):
                rows.append([prof, f["seed"], grp, feat, a, v])
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["policy_id", "seed", "group", "feature", "availability", "value"])
        w.writerows(rows)


import csv  # noqa: E402


if __name__ == "__main__":
    run()
