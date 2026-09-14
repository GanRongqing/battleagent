#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""formal_aggregate.py — aggregate, sanity checks, failure audit, figures, markdown.

Reads formal_eval_20260825/episode_results.csv and produces:
  aggregate_results.csv, failure_cases.csv, figures/*.png,
  FORMAL_EVAL_SUMMARY.md, FORMAL_EVAL_FOR_REPORT.md
"""
import csv
import json
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "formal_eval_20260825")
FIG = os.path.join(OUT, "figures")
Z = 1.96

SCEN_LABELS = {"S1": "5+5 vs 10", "S2": "10+10 vs 20", "S3": "15+15 vs 30"}
SCEN_ORDER = ["S1", "S2", "S3"]


def wilson(k, n, z=Z):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    c = (p + z * z / (2 * n)) / denom
    h = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denom
    return p, max(0.0, c - h), min(1.0, c + h)


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _mean_std(vals):
    v = [_f(x) for x in vals]
    v = [x for x in v if x is not None]
    if not v:
        return None, None
    m = sum(v) / len(v)
    s = (sum((x - m) ** 2 for x in v) / len(v)) ** 0.5
    return m, s


def classify(row):
    fr = row.get("failure_reason", "other")
    return {
        "runtime_error": "E", "breakthrough": "C", "timeout": "A",
        "resource_exhaustion": "D", "lost_track_reacquire": "B",
    }.get(fr, "F")


def sanity(episodes):
    issues = []
    n = len(episodes)
    if n != 90:
        issues.append(f"episode_results total = {n}, expected 90")
    for sid in SCEN_ORDER:
        rows = [r for r in episodes if r["scenario"] == sid]
        if len(rows) != 30:
            issues.append(f"{sid}: n={len(rows)}, expected 30")
        for r in rows:
            wu = int(_f(r["friendly_usv_initial"]))
            wuv = int(_f(r["friendly_uav_initial"]))
            bu = int(_f(r["enemy_combat_usv_initial"]))
            usv_a, usv_d = int(_f(r["friendly_usv_alive"])), int(_f(r["friendly_usv_dead"]))
            if usv_a + usv_d != wu:
                issues.append(f"{sid} s{r['seed']}: usv alive+dead {usv_a}+{usv_d} != initial {wu}")
            kill = int(_f(r["enemy_combat_usv_killed"]))
            alive = int(_f(r["enemy_combat_usv_alive_at_end"]))
            oob = int(_f(r["enemy_oob_count"]))
            brk = int(_f(r["enemy_breakthrough_count"]))
            if kill + alive + oob + brk != bu:
                issues.append(f"{sid} s{r['seed']}: killed+alive+oob+brk "
                              f"{kill}+{alive}+{oob}+{brk} != initial {bu}")
            mm = int(_f(r.get("accounting_mismatch", 0)))
            if mm > 0:
                issues.append(f"{sid} s{r['seed']}: event-vs-terminal mismatch {mm}")
            for k in ("total_explored_area_km2", "explored_ratio"):
                v = _f(r[k])
                if v is None or (isinstance(v, float) and math.isnan(v)):
                    issues.append(f"{sid} s{r['seed']}: NaN in {k}")
            er = _f(r["explored_ratio"])
            if er is not None and er < 0:
                issues.append(f"{sid} s{r['seed']}: negative explored_ratio {er}")
            if er is not None and er > 1.0001:
                issues.append(f"{sid} s{r['seed']}: explored_ratio {er} > 1")
    # duplicate seeds
    seen = {}
    for r in episodes:
        key = (r["scenario"], r["seed"])
        if key in seen:
            issues.append(f"duplicate episode: {key}")
        seen[key] = 1
    return issues


def run(out_dir=None):
    global OUT, FIG
    if out_dir:
        OUT = out_dir
        FIG = os.path.join(OUT, "figures")
    os.makedirs(FIG, exist_ok=True)
    ep = os.path.join(OUT, "episode_results.csv")
    rows = list(csv.DictReader(open(ep, encoding="utf-8")))
    issues = sanity(rows)

    agg = []
    for sid in SCEN_ORDER:
        rr = [r for r in rows if r["scenario"] == sid]
        n = len(rr)
        wins = sum(1 for r in rr if r["victory"] == "1" or r["victory"] == "True")
        cw = sum(1 for r in rr if r["clean_win"] == "1" or r["clean_win"] == "True")
        p, lo, hi = wilson(cw, n)
        brk = sum(1 for r in rr if int(_f(r["enemy_breakthrough_count"])) > 0)
        oob = sum(1 for r in rr if int(_f(r["enemy_oob_count"])) > 0)
        to = sum(1 for r in rr if int(_f(r["timeout"])) == 1)
        m_usv_d, s_usv_d = _mean_std([r["friendly_usv_dead"] for r in rr])
        m_td, _ = _mean_std([r["friendly_total_dead"] for r in rr])
        m_kill, s_kill = _mean_std([r["enemy_combat_usv_killed"] for r in rr])
        m_alive, _ = _mean_std([r["enemy_combat_usv_alive_at_end"] for r in rr])
        m_exp, s_exp = _mean_std([r["total_explored_area_km2"] for r in rr])
        m_ratio, s_ratio = _mean_std([r["explored_ratio"] for r in rr])
        m_sim, _ = _mean_std([r["sim_time"] for r in rr])
        m_wall, _ = _mean_std([r["wall_time"] for r in rr])
        agg.append({
            "scenario": sid,
            "friendly_usv": int(_f(rr[0]["friendly_usv_initial"])),
            "friendly_uav": int(_f(rr[0]["friendly_uav_initial"])),
            "enemy_combat_usv": int(_f(rr[0]["enemy_combat_usv_initial"])),
            "N": n, "wins": wins, "clean_wins": cw,
            "win_rate": round(p, 4), "clean_win_rate": round(p, 4),
            "clean_win_rate_lo95": round(lo, 4), "clean_win_rate_hi95": round(hi, 4),
            "avg_friendly_usv_dead": round(m_usv_d, 2) if m_usv_d is not None else "",
            "std_friendly_usv_dead": round(s_usv_d, 2) if s_usv_d is not None else "",
            "avg_friendly_total_dead": round(m_td, 2) if m_td is not None else "",
            "avg_enemy_combat_killed": round(m_kill, 2) if m_kill is not None else "",
            "std_enemy_combat_killed": round(s_kill, 2) if s_kill is not None else "",
            "avg_enemy_combat_alive_end": round(m_alive, 2) if m_alive is not None else "",
            "avg_explored_area_km2": round(m_exp, 1) if m_exp is not None else "",
            "std_explored_area_km2": round(s_exp, 1) if s_exp is not None else "",
            "avg_explored_ratio": round(m_ratio, 4) if m_ratio is not None else "",
            "std_explored_ratio": round(s_ratio, 4) if s_ratio is not None else "",
            "avg_sim_time": round(m_sim, 1) if m_sim is not None else "",
            "avg_wall_time": round(m_wall, 1) if m_wall is not None else "",
            "breakthrough_rate": round(brk / n, 4) if n else "",
            "oob_episode_rate": round(oob / n, 4) if n else "",
            "timeout_rate": round(to / n, 4) if n else "",
        })
    with open(os.path.join(OUT, "aggregate_results.csv"), "w", newline="",
              encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(agg[0].keys()))
        w.writeheader()
        w.writerows(agg)

    # failure cases
    fc = [r for r in rows if not (r["clean_win"] == "1" or r["clean_win"] == "True")]
    fc_cols = ["scenario", "seed", "result", "failure_type", "failure_reason",
               "friendly_dead", "enemy_killed", "enemy_alive", "breakthrough",
               "timeout", "last_known_threat_count", "last_reliable_track_time",
               "notes"]
    with open(os.path.join(OUT, "failure_cases.csv"), "w", newline="",
              encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fc_cols)
        w.writeheader()
        for r in fc:
            w.writerow({
                "scenario": r["scenario"], "seed": r["seed"], "result": r["result"],
                "failure_type": classify(r), "failure_reason": r["failure_reason"],
                "friendly_dead": r["friendly_total_dead"],
                "enemy_killed": r["enemy_combat_usv_killed"],
                "enemy_alive": r["enemy_combat_usv_alive_at_end"],
                "breakthrough": r["enemy_breakthrough_count"],
                "timeout": r["timeout"],
                "last_known_threat_count": r["remaining_combat_threats"],
                "last_reliable_track_time": "", "notes": r["initial_observation"],
            })

    figures(agg)
    write_summary(agg, issues)
    write_report(agg)
    print("aggregate done. issues:", issues if issues else "NONE")
    return issues


def _style():
    plt.rcParams.update({"figure.facecolor": "white", "axes.facecolor": "white",
                         "savefig.facecolor": "white", "font.size": 11,
                         "axes.grid": True, "grid.alpha": 0.25})


def figures(agg):
    _style()
    labels = [SCEN_LABELS[a["scenario"]] for a in agg]
    xs = range(len(agg))

    def ci(a, key):
        lo = a["clean_win_rate_lo95"] if key == "clean" else a["clean_win_rate"]
        hi = a["clean_win_rate_hi95"] if key == "clean" else a["clean_win_rate"]
        return lo, hi

    # 01 clean win rate
    vals = [a["clean_win_rate"] for a in agg]
    errs = [[a["clean_win_rate"] - a["clean_win_rate_lo95"] for a in agg],
            [a["clean_win_rate_hi95"] - a["clean_win_rate"] for a in agg]]
    plt.figure(figsize=(6, 4))
    plt.bar(xs, vals, yerr=errs, capsize=5, color="#4472C4", alpha=0.9)
    plt.xticks(list(xs), labels)
    plt.ylim(0, 1)
    plt.ylabel("Clean Win Rate")
    plt.title("Clean Win Rate by Scale (N=30)")
    for x, v in zip(xs, vals):
        plt.text(x, v + 0.02, f"{v:.2f}", ha="center")
    plt.tight_layout(); plt.savefig(os.path.join(FIG, "01_clean_win_rate.png"), dpi=300)
    plt.close()

    # 02 friendly USV loss
    vals = [a["avg_friendly_usv_dead"] for a in agg]
    errs = [a["std_friendly_usv_dead"] for a in agg]
    plt.figure(figsize=(6, 4))
    plt.bar(xs, vals, yerr=errs, capsize=5, color="#C44E52", alpha=0.9)
    plt.xticks(list(xs), labels)
    plt.ylabel("Friendly USV Lost (mean ± SD)")
    plt.title("Friendly USV Loss by Scale (N=30)")
    for x, v in zip(xs, vals):
        plt.text(x, v + 0.3, f"{v:.1f}", ha="center")
    plt.tight_layout(); plt.savefig(os.path.join(FIG, "02_friendly_loss.png"), dpi=300)
    plt.close()

    # 03 enemy kills
    vals = [a["avg_enemy_combat_killed"] for a in agg]
    errs = [a["std_enemy_combat_killed"] for a in agg]
    plt.figure(figsize=(6, 4))
    plt.bar(xs, vals, yerr=errs, capsize=5, color="#4CAF50", alpha=0.9)
    plt.xticks(list(xs), labels)
    plt.ylabel("Enemy Combat USV Killed (mean ± SD)")
    plt.title("Enemy Combat Kills by Scale (N=30)")
    for x, v in zip(xs, vals):
        plt.text(x, v + 0.4, f"{v:.1f}", ha="center")
    plt.tight_layout(); plt.savefig(os.path.join(FIG, "03_enemy_kills.png"), dpi=300)
    plt.close()

    # 04 exploration area
    vals = [a["avg_explored_area_km2"] for a in agg]
    errs = [a["std_explored_area_km2"] for a in agg]
    plt.figure(figsize=(6, 4))
    plt.bar(xs, vals, yerr=errs, capsize=5, color="#FFC000", alpha=0.9)
    plt.xticks(list(xs), labels)
    plt.ylabel("Explored Area (km², mean ± SD)")
    plt.title("Explored Area by Scale (N=30)")
    for x, v in zip(xs, vals):
        plt.text(x, v + 300, f"{v:,.0f}", ha="center")
    plt.tight_layout(); plt.savefig(os.path.join(FIG, "04_exploration_area.png"), dpi=300)
    plt.close()

    # 05 exploration ratio
    vals = [a["avg_explored_ratio"] for a in agg]
    errs = [a["std_explored_ratio"] for a in agg]
    plt.figure(figsize=(6, 4))
    plt.bar(xs, vals, yerr=errs, capsize=5, color="#7030A0", alpha=0.9)
    plt.xticks(list(xs), labels)
    plt.ylim(0, 1)
    plt.ylabel("Explored Ratio (mean ± SD)")
    plt.title("Explored Ratio by Scale (N=30)")
    for x, v in zip(xs, vals):
        plt.text(x, v + 0.01, f"{v:.3f}", ha="center")
    plt.tight_layout(); plt.savefig(os.path.join(FIG, "05_exploration_ratio.png"), dpi=300)
    plt.close()


def write_summary(agg, issues):
    lines = []
    lines.append("# Formal Evaluation Summary — S1/S2/S3 (N=30 each, 90 episodes)\n")
    lines.append("## Main table\n")
    lines.append("| 场景 | N | Clean Win | 95% CI | 平均击杀 | 平均我方USV损失 | 平均探索面积(km²) | 探索比例 | Breakthrough | OOB |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for a in agg:
        lines.append(f"| {SCEN_LABELS[a['scenario']]} | {a['N']} | {a['clean_wins']} | "
                     f"[{a['clean_win_rate_lo95']}, {a['clean_win_rate_hi95']}] | "
                     f"{a['avg_enemy_combat_killed']} | {a['avg_friendly_usv_dead']} | "
                     f"{a['avg_explored_area_km2']} | {a['avg_explored_ratio']} | "
                     f"{int(float(a['breakthrough_rate']) * a['N'])} | "
                     f"{int(float(a['oob_episode_rate']) * a['N'])} |")
    lines.append("")
    lines.append("## Definitions\n")
    lines.append("- Clean Win = engine `Result.Victory` (black_ship_alive==0, i.e. all enemy combat USV destroyed) **and** `black_breakthrough==0` (existing run_priority_eval definition).")
    lines.append("- 平均击杀 = **event-based reconciled** enemy combat USV killed (reward `black_killed` minus breakthrough minus OOB; cross-checked with agent `[KILL]` names).")
    lines.append("- Exploration = maritime_metrics fixed 5 km grid, union-dedup; denominator = 任务区域.json polygon area (193,301.27 km²).")
    lines.append("- OOB removal fraction computed from evaluator out-of-bounds flags.")
    lines.append("")
    lines.append("## Consistency check\n")
    if issues:
        lines.append("Issues found:\n")
        for i in issues:
            lines.append(f"- {i}")
    else:
        lines.append("All checks PASS: 30 episodes per scenario (90 total); "
                     "friendly alive+dead == initial; enemy killed+alive+oob+brk == initial; "
                     "no NaN / duplicate seed / negative or >1 explored_ratio.")
    lines.append("")
    lines.append("## OOB\n")
    total_oob = sum(1 for a in agg for _ in range(int(float(a['oob_episode_rate']) * a['N'])))
    if total_oob == 0:
        lines.append("No observed enemy OOB removals in the formal evaluation.")
    else:
        lines.append(f"Enemy OOB episodes: {total_oob}")
    with open(os.path.join(OUT, "FORMAL_EVAL_SUMMARY.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def write_report(agg):
    lines = ["# 正式实验统计", "", "## Experimental Setup", "",
             "- Frozen Agent: agent_hybrid_v5.py (hash in config_manifest.json)",
             "- Frozen Skill: skills/maritime_commander/SKILL.md (hash in config_manifest.json)",
             "- Random-waypoint enemy movement, fixed_frontage, seed 1001–1030 per scale",
             "- N = 30 per setting, total 90 episodes", "", "## Main Results", ""]
    lines.append("| 场景 | N | Clean Win | 95% CI | 平均击杀 | 平均USV损失 | 探索面积km² | 探索比例 | Breakthrough | OOB |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for a in agg:
        lines.append(f"| {SCEN_LABELS[a['scenario']]} | {a['N']} | {a['clean_wins']} | "
                     f"[{a['clean_win_rate_lo95']}, {a['clean_win_rate_hi95']}] | "
                     f"{a['avg_enemy_combat_killed']} | {a['avg_friendly_usv_dead']} | "
                     f"{a['avg_explored_area_km2']} | {a['avg_explored_ratio']} | "
                     f"{int(float(a['breakthrough_rate']) * a['N'])} | "
                     f"{int(float(a['oob_episode_rate']) * a['N'])} |")
    lines.append("")
    lines.append("## Key Findings")
    lines.append("")
    cw = [a["clean_win_rate"] for a in agg]
    lines.append(f"- Clean win rate: S1 {cw[0]:.2f} → S2 {cw[1]:.2f} → S3 {cw[2]:.2f} (N=30 each; "
                 "reporting observed rates, no statistical generalization claimed).")
    lines.append(f"- Friendly USV loss (mean): S1 {agg[0]['avg_friendly_usv_dead']} → "
                 f"S2 {agg[1]['avg_friendly_usv_dead']} → S3 {agg[2]['avg_friendly_usv_dead']}.")
    lines.append(f"- Enemy combat USV killed (mean, event-based): S1 {agg[0]['avg_enemy_combat_killed']} → "
                 f"S2 {agg[1]['avg_enemy_combat_killed']} → S3 {agg[2]['avg_enemy_combat_killed']}.")
    lines.append(f"- Explored area (mean km²): S1 {agg[0]['avg_explored_area_km2']} → "
                 f"S2 {agg[1]['avg_explored_area_km2']} → S3 {agg[2]['avg_explored_area_km2']}; "
                 f"explored ratio {agg[0]['avg_explored_ratio']} → {agg[1]['avg_explored_ratio']} → {agg[2]['avg_explored_ratio']}.")
    lines.append("- Failure modes: see failure_cases.csv (auto-classified from auditable evidence only).")
    lines.append("- OOB: see FORMAL_EVAL_SUMMARY.md (reported as observed in formal eval only).")
    lines.append("")
    lines.append("> N=30 per setting. Results reported as observed; no over-generalization beyond this sample.")
    with open(os.path.join(OUT, "FORMAL_EVAL_FOR_REPORT.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    run()
