#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""coevolution_final/analyze.py — three-stage co-evolution FINAL analysis.

Reads final_episode_results.csv (+ optional_w6_b0_regression.csv) and produces:
  stage_aggregate.csv, stage_paired_deltas.csv, w6_mechanism_stats.csv
  tables/table1_three_stage.{csv,md}, table2_w6_mechanisms.{csv,md}, table3_evolution_stages.md
  figures/figure_three_stage_*.png   (300 dpi, grayscale-friendly)
  0-based paired bootstrap 95% CI on the two core deltas (offline resampling, N=10).

Stages: Stage0=W5xB0, Stage1=W5xB3, Stage2=W6xB3.  Scales S1/S2/S3. N=10 holdout.
"""
import csv
import json
import math
import os
import random
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

OUT = os.path.dirname(os.path.abspath(__file__))
EPI = os.path.join(OUT, "final_episode_results.csv")
FIG = os.path.join(OUT, "figures")
TAB = os.path.join(OUT, "tables")
os.makedirs(FIG, exist_ok=True)
os.makedirs(TAB, exist_ok=True)

SCALES = ["S1", "S2", "S3"]
STAGES = ["Stage0", "Stage1", "Stage2"]
STAGE_LABEL = {"Stage0": "Initial (W5xB0)", "Stage1": "Black Evolved (W5xB3)",
               "Stage2": "White Adapted (W6xB3)"}
METRICS = {
    "clean_win": ("Clean Win Rate", "higher"),
    "enemy_combat_kills": ("Enemy Combat Kills", "higher"),
    "friendly_usv_dead": ("Friendly USV Loss", "lower"),
    "breakthrough": ("Breakthrough Rate", "lower"),
    "explored_area_km2": ("Explored Area (km2)", "lower"),
    "resolution_time_s": ("Resolution Time (s)", "lower"),
}
UTIL = {k: (1 if v[1] == "higher" else -1) for k, v in METRICS.items()}


def load(path):
    rows = list(csv.DictReader(open(path)))
    for r in rows:
        for k in ("clean_win", "enemy_combat_kills", "friendly_usv_dead", "breakthrough",
                  "resolution_time_s"):
            r[k] = float(r[k])
        r["explored_area_km2"] = float(r["explored_area_km2"] or 0)
    return rows


def bootstrap_ci(pairs, util=1, n_iter=4000, seed=7):
    """pairs: list of (stage1_val, stage2_val); return (mean_delta, lo, hi) on the
    'higher is better' scale via utility transform."""
    rng = random.Random(seed)
    deltas = [util * (b - a) for (a, b) in pairs]
    n = len(deltas)
    if n == 0:
        return None
    mean = sum(deltas) / n
    boots = []
    for _ in range(n_iter):
        s = sum(rng.choice(deltas) for _ in range(n)) / n
        boots.append(s)
    boots.sort()
    return mean, boots[int(0.025 * n_iter)], boots[int(0.975 * n_iter)]


def stage_map(rows):
    m = {}
    for r in rows:
        m[(r["scenario"], r["stage"], int(r["seed"]))] = r
    return m


def main():
    rows = load(EPI)
    smap = stage_map(rows)
    missing = [(sc, st, sd) for sc in SCALES for st in STAGES for sd in range(4001, 4011)
               if (sc, st, sd) not in smap]
    if missing:
        print("[WARN] missing episodes:", len(missing), missing[:5])
    print("episodes loaded:", len(rows))

    # ── aggregate ──
    agg_path = os.path.join(OUT, "stage_aggregate.csv")
    with open(agg_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["scenario", "stage", "stage_label", "N", "clean_win", "clean_rate",
                    "enemy_combat_kills", "friendly_usv_dead", "breakthrough",
                    "breakthrough_rate", "explored_area_km2", "resolution_time_s"])
        for sc in SCALES:
            for st in STAGES:
                sub = [r for r in rows if r["scenario"] == sc and r["stage"] == st]
                n = len(sub)
                w.writerow([sc, st, STAGE_LABEL[st], n,
                            sum(r["clean_win"] for r in sub),
                            (sum(r["clean_win"] for r in sub) / n) if n else 0,
                            sum(r["enemy_combat_kills"] for r in sub) / n,
                            sum(r["friendly_usv_dead"] for r in sub) / n,
                            sum(r["breakthrough"] for r in sub),
                            (sum(r["breakthrough"] for r in sub) / n) if n else 0,
                            sum(r["explored_area_km2"] for r in sub) / n,
                            sum(r["resolution_time_s"] for r in sub) / n])
    print("wrote", agg_path)

    # ── paired deltas (same seed) ──
    delta_path = os.path.join(OUT, "stage_paired_deltas.csv")
    rows_out = []
    for sc in SCALES:
        for m in METRICS:
            db = []   # black evolution delta (S1-S0)
            dw = []   # white adaptation delta (S2-S1)
            for sd in range(4001, 4011):
                r0, r1, r2 = smap.get((sc, "Stage0", sd)), smap.get((sc, "Stage1", sd)), \
                             smap.get((sc, "Stage2", sd))
                if not (r0 and r1 and r2):
                    continue
                db.append(r1[m] - r0[m])
                dw.append(r2[m] - r1[m])
            mean_db = sum(db) / len(db)
            mean_dw = sum(dw) / len(dw)
            med_db = sorted(db)[len(db) // 2]
            med_dw = sorted(dw)[len(dw) // 2]
            ci_b = bootstrap_ci(list(zip([0] * len(db), db)), util=UTIL[m])
            ci_w = bootstrap_ci(list(zip([0] * len(dw), dw)), util=UTIL[m])
            rows_out.append([sc, m, METRICS[m][0], "N=10 paired seeds",
                             round(mean_db, 3), round(med_db, 3), round(mean_dw, 3),
                             round(med_dw, 3),
                             f"[{ci_b[1]:.3f},{ci_b[2]:.3f}]" if ci_b else "",
                             f"[{ci_w[1]:.3f},{ci_w[2]:.3f}]" if ci_w else ""])
    with open(delta_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["scenario", "metric", "metric_name", "note",
                    "mean_delta_black(S1-S0)", "median_delta_black",
                    "mean_delta_white(S2-S1)", "median_delta_white",
                    "boot95CI_black_on_utility", "boot95CI_white_on_utility"])
        w.writerows(rows_out)
    print("wrote", delta_path)

    # ── w6 mechanism stats (Stage2 only) ──
    mech_cols = ["unique_intercept_plan_changes", "unsafe_close_entries",
                 "unsafe_close_duration_steps", "reposition_outward_count",
                 "handoff_count", "successful_handoff_count", "handoff_evaluations",
                 "track_maintenance_assignments", "screen_assignments",
                 "screen_evaluations", "unique_screen_reconfigurations",
                 "unique_high_risk_transitions", "critical_risk_entries",
                 "late_intercept_events", "breakthrough_risk_alerts",
                 "min_target_distance_during_pursuit"]
    w6path = os.path.join(OUT, "w6_mechanism_stats.csv")
    with open(w6path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["scenario", "metric"] + STAGES + ["note"])
        for sc in SCALES:
            for c in mech_cols:
                vals = [0.0] * 3
                for i, st in enumerate(STAGES):
                    sub = [float(r.get(c, 0) or 0) for r in rows
                           if r["scenario"] == sc and r["stage"] == st]
                    vals[i] = sum(sub) / len(sub) if sub else 0.0
                w.writerow([sc, c] + [round(v, 2) for v in vals] +
                           ["Stage2 only interpretable (W6)"])
    print("wrote", w6path)

    # ── TABLE 1 ──
    t1csv = os.path.join(TAB, "table1_three_stage.csv")
    agg = {(r["scenario"], r["stage"]): r for r in csv.DictReader(open(agg_path))}
    def aval(sc, st, m):
        r = agg[(sc, st)]
        if m == "clean_win":
            return float(r["clean_rate"])
        if m == "breakthrough":
            return float(r["breakthrough_rate"])
        return float(r[m])
    with open(t1csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Scale", "Metric", "Stage0 Initial W5xB0", "Stage1 Black Evolved W5xB3",
                    "Stage2 White Adapted W6xB3", "Delta Black Evolution (S1-S0)",
                    "Delta White Adaptation (S2-S1)"])
        for sc in SCALES:
            for m, (name, _dir) in METRICS.items():
                rate = m in ("clean_win", "breakthrough")
                a, b, c = aval(sc, "Stage0", m), aval(sc, "Stage1", m), aval(sc, "Stage2", m)
                fmt = (lambda v: f"{v:.2f}") if rate else (lambda v: f"{v:.1f}")
                w.writerow([sc, name, fmt(a), fmt(b), fmt(c),
                            f"{b - a:+.2f}" if rate else f"{b - a:+.1f}",
                            f"{c - b:+.2f}" if rate else f"{c - b:+.1f}"])
    print("wrote", t1csv)

    # ── TABLE 2 (Stage 2 W6 mechanisms, mean per episode, transposed) ──
    t2csv = os.path.join(TAB, "table2_w6_mechanisms.csv")
    keep = ["unique_intercept_plan_changes", "unsafe_close_entries",
            "handoff_count", "successful_handoff_count",
            "track_maintenance_assignments", "unique_screen_reconfigurations",
            "screen_assignments", "unique_high_risk_transitions",
            "critical_risk_entries", "late_intercept_events"]
    mech_mean = {c: [] for c in keep}
    for sc in SCALES:
        sub = [r for r in rows if r["scenario"] == sc and r["stage"] == "Stage2"]
        for c in keep:
            mech_mean[c].append(sum(float(r.get(c, 0) or 0) for r in sub) / len(sub)
                                if sub else 0.0)
    with open(t2csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Mechanism (Stage2, mean/episode)", "S1", "S2", "S3"])
        for c in keep:
            w.writerow([c] + [round(v, 2) for v in mech_mean[c]])
    print("wrote", t2csv)

    # ── figures ──
    draw = [("clean_win", "Clean Win Rate", "rate", "clean"), ("friendly_usv_dead", "Friendly USV Loss",
            "count", "loss"), ("breakthrough", "Breakthrough Rate", "rate", "breakthrough"),
            ("explored_area_km2", "Explored Area", "km2", "exploration"),
            ("resolution_time_s", "Resolution Time", "seconds", "resolution")]
    for m, title, unit, tag in draw:
        fig, ax = plt.subplots(figsize=(6, 4), dpi=300)
        for i, sc in enumerate(SCALES):
            vals = []
            for st in STAGES:
                sub = [r for r in rows if r["scenario"] == sc and r["stage"] == st]
                vals.append(sum(r[m] for r in sub) / len(sub) if sub else 0)
            mk = ["o", "s", "^", "D"][i]
            ax.plot(range(3), vals, marker=mk, label=sc, color="black", lw=1.6)
        ax.set_xticks(range(3))
        ax.set_xticklabels(["Initial\nW5xB0", "Black Evolved\nW5xB3", "White Adapted\nW6xB3"])
        ax.set_ylabel(unit)
        ax.set_title(title)
        ax.legend(frameon=False)
        ax.grid(True, linestyle=":", alpha=0.5)
        fig.tight_layout()
        fig.savefig(os.path.join(FIG, f"figure_three_stage_{tag}.png"), dpi=300)
        plt.close(fig)
    print("figures written to", FIG)

    print("[done] analyze complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
