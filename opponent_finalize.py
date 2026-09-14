#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""opponent_finalize.py — finalize the B0 vs B3 formal comparison.

Merges:
  B0 column : reused frozen formal run (formal_eval_20260825/episode_results.csv) +
              pressure metrics computed from API game logs (same definitions as live B3).
  B3 column : fresh runs from opponent_formal_eval/episode_results.csv (live pressure +
              B3 adaptive event counters).

Produces aggregate_results.csv, paired_results.csv, failure_cases.csv, figures/*.png,
FORMAL_OPPONENT_EVAL.md, FORMAL_OPPONENT_EVAL_FOR_REPORT.md.
"""
import csv
import json
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "opponent_formal_eval")
FIG = os.path.join(OUT, "figures")
GAMELOG_DIR = os.path.join(ROOT, "hsystem", "pomdp_api", "api_logs", "games")
FORMAL_B0_CSV = os.path.join(ROOT, "formal_eval_20260825", "episode_results.csv")
B3_CSV = os.path.join(OUT, "episode_results.csv")
Z = 1.96

SCEN_LABELS = {"S1": "5+5 vs10", "S2": "10+10 vs20", "S3": "15+15 vs30"}
PROF_LABELS = {"B0_RANDOM": "B0", "B3_ADAPTIVE": "B3"}

PRESSURE_KEYS = ["peak_simultaneous_threat_count", "mean_simultaneous_threat_count",
                 "approach_lane_entropy", "active_group_count_mean", "active_group_count_peak",
                 "mean_group_spacing_km", "time_to_first_detection", "time_to_first_engagement",
                 "time_to_first_kill", "time_to_resolve_all_combat_threats",
                 "peak_active_engagements", "mean_active_engagements",
                 "peak_uncovered_hostile_tracks", "mean_uncovered_hostile_tracks",
                 "time_with_zero_reliable_tracks_steps"]


def wilson(k, n, z=Z):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / d
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


# ── game-log indexing for B0 pressure metrics ──
def _to_epoch(ts):
    import datetime
    try:
        return datetime.datetime.strptime(str(ts), "%Y-%m-%d %H:%M:%S").timestamp()
    except Exception:
        return None


def index_game_logs(date_prefixes=("20260825", "20260826", "20260827")):
    import glob
    idx = []
    for p in sorted(glob.glob(os.path.join(GAMELOG_DIR, "game_*.json"))):
        base = os.path.basename(p)
        if date_prefixes and not any(dp in base for dp in date_prefixes):
            continue
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        if "steps" not in d or not d["steps"]:
            continue
        idx.append({"path": p,
                    "end_epoch": _to_epoch(d.get("end_real_time")),
                    "last_sim": d["steps"][-1].get("sim_time"),
                    "start": d.get("start_real_time", ""),
                    "result": d.get("result")})
    return idx


def compute_b0_pressure(episode, log_index, used):
    """Match one B0 episode to a game log by agent-log mtime vs game_log end_real_time."""
    import os as _os
    logf = os.path.join(ROOT, "logs_formal", f"{episode['scenario']}_s{episode['seed']}.log")
    try:
        mtime = os.path.getmtime(logf)
    except OSError:
        return {}, None
    best = None
    for i, lg in enumerate(log_index):
        if i in used or lg["end_epoch"] is None:
            continue
        d = abs(lg["end_epoch"] - mtime)
        if d <= 900.0 and (best is None or d < best[0]):
            best = (d, i, lg)
    if best is None:
        return {}, None
    used.add(best[1])
    import opponent_pressure_from_log as opl
    d = json.load(open(best[2]["path"], encoding="utf-8"))
    try:
        pres = opl.pressure_from_game_log(d["steps"], int(_f(episode["enemy_combat_usv_initial"])))
    except Exception:
        pres = {}
    return pres, best[2]["path"]


def load_b0():
    rows = list(csv.DictReader(open(FORMAL_B0_CSV, encoding="utf-8")))
    idx = index_game_logs()
    used = set()
    out = []
    cache = os.path.join(OUT, "b0_pressure_cache.csv")
    cache_map = {}
    if os.path.exists(cache):
        for r in csv.DictReader(open(cache)):
            cache_map[(r["scenario"], r["seed"])] = r
    for r in rows:
        key = (r["scenario"], r["seed"])
        pressure = cache_map.get(key)
        if pressure is None:
            pressure, _ = compute_b0_pressure(r, idx, used)
            if not pressure:
                pressure = {k: None for k in PRESSURE_KEYS}
        row = {
            "experiment_id": "formal_b0b3", "scenario": r["scenario"], "scale": r["scenario"],
            "opponent_profile": "B0_RANDOM", "seed": int(r["seed"]),
            "friendly_usv_initial": int(_f(r["friendly_usv_initial"])),
            "friendly_uav_initial": int(_f(r["friendly_uav_initial"])),
            "enemy_combat_usv_initial": int(_f(r["enemy_combat_usv_initial"])),
            "enemy_uav_initial": 0,
            "result": r["result"], "victory": int(r["victory"] == "1" or r["victory"] == "True"),
            "clean_win": int(r["clean_win"] == "1" or r["clean_win"] == "True"),
            "failure_reason": r["failure_reason"],
            "sim_time": round(_f(r["sim_time"]), 1), "wall_time": round(_f(r["wall_time"]), 1),
            "friendly_usv_dead": int(_f(r["friendly_usv_dead"])),
            "friendly_uav_dead": int(_f(r["friendly_uav_dead"])),
            "friendly_total_dead": int(_f(r["friendly_total_dead"])),
            "enemy_combat_killed_event": int(_f(r["enemy_combat_kills_event_based"])),
            "enemy_combat_killed_terminal": int(_f(r["enemy_combat_kills_terminal_observed"])),
            "enemy_combat_alive_end": int(_f(r["enemy_combat_usv_alive_at_end"])),
            "kill_accounting_mismatch": int(_f(r["accounting_mismatch"])),
            "enemy_breakthrough_count": int(_f(r["enemy_breakthrough_count"])),
            "enemy_oob_count": int(_f(r["enemy_oob_count"])),
            "timeout": int(r["timeout"] == "1" or r["timeout"] == "True"),
            "explored_area_km2": _f(r["total_explored_area_km2"]),
            "explored_ratio": _f(r["explored_ratio"]),
            "usv_explored_area_km2": _f(r["usv_explored_area_km2"]),
            "uav_explored_area_km2": _f(r["uav_explored_area_km2"]),
            "damage_hits": int(_f(r["damage_hits"])), "locks_started": int(_f(r["locks_started"])),
            "locks_broken": int(_f(r["locks_broken"])),
            "global_reacquire_count": r.get("global_reacquire_entries"),
            "http_or_trace_errors": int(_f(r.get("http_or_trace_errors"))),
            "agent_rc": r.get("agent_rc"),
            "b3_replan_count": 0, "b3_lane_shift_count": 0,
            "b3_dispersion_event_count": 0, "b3_detected_white_event_count": 0,
        }
        for k in PRESSURE_KEYS:
            row[k] = pressure.get(k)
        out.append(row)
    # write pressure cache (avoid recomputing game-log loads every finalize)
    try:
        import csv as _csv
        with open(cache, "w", newline="", encoding="utf-8") as f:
            w = _csv.DictWriter(f, fieldnames=["scenario", "seed"] + PRESSURE_KEYS)
            w.writeheader()
            for r in out:
                row = {"scenario": r["scenario"], "seed": r["seed"]}
                for k in PRESSURE_KEYS:
                    row[k] = r.get(k)
                w.writerow(row)
    except Exception:
        pass
    return out


def load_b3():
    rows = list(csv.DictReader(open(B3_CSV, encoding="utf-8")))
    return [r for r in rows if r.get("opponent_profile") == "B3_ADAPTIVE"]


def load_all():
    b0 = load_b0()
    b3 = load_b3()
    # normalize types for b3 rows
    for r in b3:
        for k in ("friendly_usv_dead", "friendly_uav_dead", "friendly_total_dead",
                  "enemy_combat_killed_event", "enemy_combat_killed_terminal",
                  "enemy_combat_alive_end", "kill_accounting_mismatch",
                  "enemy_breakthrough_count", "enemy_oob_count", "timeout", "victory",
                  "clean_win", "damage_hits", "locks_started", "locks_broken",
                  "http_or_trace_errors"):
            v = r.get(k)
            r[k] = int(_f(v)) if _f(v) is not None else 0
        for k in ("sim_time", "wall_time", "explored_area_km2", "explored_ratio",
                  "usv_explored_area_km2", "uav_explored_area_km2",
                  "peak_simultaneous_threat_count", "mean_simultaneous_threat_count",
                  "approach_lane_entropy", "active_group_count_mean",
                  "active_group_count_peak", "mean_group_spacing_km",
                  "time_to_first_detection", "time_to_first_engagement",
                  "time_to_first_kill", "time_to_resolve_all_combat_threats",
                  "peak_active_engagements", "mean_active_engagements",
                  "peak_uncovered_hostile_tracks", "mean_uncovered_hostile_tracks"):
            v = r.get(k)
            r[k] = _f(v) if _f(v) is not None else None
        for k in ("b3_replan_count", "b3_lane_shift_count", "b3_dispersion_event_count",
                  "b3_detected_white_event_count"):
            v = r.get(k)
            r[k] = int(_f(v)) if _f(v) is not None else 0
        r["seed"] = int(r["seed"])
        r["friendly_usv_initial"] = int(_f(r["friendly_usv_initial"]))
        r["enemy_combat_usv_initial"] = int(_f(r["enemy_combat_usv_initial"]))
    all_rows = b0 + b3
    # per-episode CSV
    cols = list(all_rows[0].keys())
    with open(os.path.join(OUT, "episode_results.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in all_rows:
            w.writerow({k: r.get(k) for k in cols})
    # per-scenario-per-profile CSVs
    for sid in ("S1", "S2", "S3"):
        wu = int(_f([r for r in all_rows if r["scenario"] == sid][0]["friendly_usv_initial"]))
        wuv = int(_f([r for r in all_rows if r["scenario"] == sid][0]["friendly_uav_initial"]))
        bu = int(_f([r for r in all_rows if r["scenario"] == sid][0]["enemy_combat_usv_initial"]))
        for prof in ("B0_RANDOM", "B3_ADAPTIVE"):
            pn = "b0" if prof == "B0_RANDOM" else "b3"
            fn = os.path.join(OUT, f"{sid.lower()}_{wu}p{wuv}_vs{bu}_{pn}.csv")
            rr = [r for r in all_rows if r["scenario"] == sid and r["opponent_profile"] == prof]
            with open(fn, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=cols)
                w.writeheader()
                for r in rr:
                    w.writerow({k: r.get(k) for k in cols})
    return all_rows


# ════════════════════════════════════════════════════════════════
def sanity(rows):
    issues = []
    mismatch_count = 0
    for sid in ("S1", "S2", "S3"):
        for prof in ("B0_RANDOM", "B3_ADAPTIVE"):
            rr = [r for r in rows if r["scenario"] == sid and r["opponent_profile"] == prof]
            if len(rr) != 30:
                issues.append(f"{sid}-{prof}: n={len(rr)} != 30")
    if len(rows) != 180:
        issues.append(f"total {len(rows)} != 180")
    seen = set()
    for r in rows:
        key = (r["scenario"], r["opponent_profile"], int(r["seed"]))
        if key in seen:
            issues.append(f"dup {key}")
        seen.add(key)
        wu = int(r["friendly_usv_initial"])
        bu = int(r["enemy_combat_usv_initial"])
        usv_dead = int(r["friendly_usv_dead"])
        kill = int(r["enemy_combat_killed_event"])
        alive = int(r["enemy_combat_alive_end"])
        oob = int(r["enemy_oob_count"])
        brk = int(r["enemy_breakthrough_count"])
        if kill + alive + oob + brk != bu:
            issues.append(f"{key}: killed+alive+oob+brk {kill}+{alive}+{oob}+{brk} != {bu}")
        mismatch_count += int(r.get("kill_accounting_mismatch", 0))
        er = _f(r.get("explored_ratio"))
        if er is not None and (er < 0 or er > 1.0001):
            issues.append(f"{key}: explored_ratio {er}")
    issues.append(f"kill_accounting_mismatch_total={mismatch_count} "
                  "(event-vs-terminal lag; event-based reconciled count is authoritative)")
    return issues


def _row_mean(rr, key):
    v = [_f(r.get(key)) for r in rr]
    v = [x for x in v if x is not None]
    return sum(v) / len(v) if v else None


def _row_std(rr, key):
    m = _row_mean(rr, key)
    v = [_f(r.get(key)) for r in rr]
    v = [x for x in v if x is not None]
    if m is None or not v:
        return None
    return (sum((x - m) ** 2 for x in v) / len(v)) ** 0.5


def aggregate(rows):
    agg = []
    for sid in ("S1", "S2", "S3"):
        for prof in ("B0_RANDOM", "B3_ADAPTIVE"):
            rr = [r for r in rows if r["scenario"] == sid and r["opponent_profile"] == prof]
            n = len(rr)
            cw = sum(1 for r in rr if r["clean_win"] == 1)
            wins = sum(1 for r in rr if r["victory"] == 1)
            p, lo, hi = wilson(cw, n)
            brk = sum(1 for r in rr if int(r["enemy_breakthrough_count"]) > 0)
            oob = sum(1 for r in rr if int(r["enemy_oob_count"]) > 0)
            to = sum(1 for r in rr if int(r["timeout"]) == 1)
            def mm(k): return round(_row_mean(rr, k), 3) if _row_mean(rr, k) is not None else ""
            def sd(k): return round(_row_std(rr, k), 3) if _row_std(rr, k) is not None else ""
            agg.append({
                "scenario": sid, "opponent_profile": prof, "N": n,
                "wins": wins, "clean_wins": cw, "clean_win_rate": round(p, 4),
                "clean_win_ci95_low": round(lo, 4), "clean_win_ci95_high": round(hi, 4),
                "avg_enemy_combat_killed": mm("enemy_combat_killed_event"),
                "std_enemy_combat_killed": sd("enemy_combat_killed_event"),
                "avg_friendly_usv_dead": mm("friendly_usv_dead"),
                "std_friendly_usv_dead": sd("friendly_usv_dead"),
                "avg_friendly_total_dead": mm("friendly_total_dead"),
                "std_friendly_total_dead": sd("friendly_total_dead"),
                "avg_explored_area_km2": mm("explored_area_km2"),
                "std_explored_area_km2": sd("explored_area_km2"),
                "avg_explored_ratio": mm("explored_ratio"),
                "std_explored_ratio": sd("explored_ratio"),
                "avg_peak_simultaneous_threat_count": mm("peak_simultaneous_threat_count"),
                "std_peak_simultaneous_threat_count": sd("peak_simultaneous_threat_count"),
                "avg_mean_simultaneous_threat_count": mm("mean_simultaneous_threat_count"),
                "avg_time_to_first_detection": mm("time_to_first_detection"),
                "avg_time_to_first_kill": mm("time_to_first_kill"),
                "avg_time_to_resolve": mm("time_to_resolve_all_combat_threats"),
                "avg_global_reacquire_count": mm("global_reacquire_count"),
                "breakthrough_rate": round(brk / n, 4) if n else "",
                "oob_episode_rate": round(oob / n, 4) if n else "",
                "timeout_rate": round(to / n, 4) if n else "",
                "avg_sim_time": mm("sim_time"), "avg_wall_time": mm("wall_time"),
            })
    with open(os.path.join(OUT, "aggregate_results.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(agg[0].keys()))
        w.writeheader(); w.writerows(agg)
    return agg


def paired(rows):
    pr = []
    deltas = {s: {"clean": [], "loss": [], "expl": [], "peak": [], "resolve": []}
              for s in ("S1", "S2", "S3")}
    for sid in ("S1", "S2", "S3"):
        b0 = {int(r["seed"]): r for r in rows if r["scenario"] == sid and r["opponent_profile"] == "B0_RANDOM"}
        b3 = {int(r["seed"]): r for r in rows if r["scenario"] == sid and r["opponent_profile"] == "B3_ADAPTIVE"}
        for sd in sorted(b0):
            if sd not in b3:
                continue
            a, b = b0[sd], b3[sd]
            def _d(k):
                va, vb = _f(a.get(k)), _f(b.get(k))
                if va is None or vb is None:
                    return None
                return vb - va
            d_clean = int(b["clean_win"]) - int(a["clean_win"])
            d_loss = _d("friendly_usv_dead")
            d_expl = _d("explored_area_km2")
            d_peak = _d("peak_simultaneous_threat_count")
            d_res = _d("time_to_resolve_all_combat_threats")
            d_kill = _d("enemy_combat_killed_event")
            pr.append({
                "scale": sid, "seed": sd,
                "b0_clean_win": int(a["clean_win"]), "b3_clean_win": int(b["clean_win"]),
                "delta_clean_win": d_clean,
                "b0_friendly_usv_dead": _f(a["friendly_usv_dead"]),
                "b3_friendly_usv_dead": _f(b["friendly_usv_dead"]),
                "delta_friendly_usv_dead": d_loss,
                "b0_enemy_killed": _f(a["enemy_combat_killed_event"]),
                "b3_enemy_killed": _f(b["enemy_combat_killed_event"]),
                "delta_enemy_killed": d_kill,
                "b0_explored_area": _f(a["explored_area_km2"]),
                "b3_explored_area": _f(b["explored_area_km2"]),
                "delta_explored_area": d_expl,
                "b0_peak_simultaneous_threat": _f(a["peak_simultaneous_threat_count"]),
                "b3_peak_simultaneous_threat": _f(b["peak_simultaneous_threat_count"]),
                "delta_peak_simultaneous_threat": d_peak,
                "b0_resolution_time": _f(a["time_to_resolve_all_combat_threats"]),
                "b3_resolution_time": _f(b["time_to_resolve_all_combat_threats"]),
                "delta_resolution_time": d_res,
            })
            for k, v in (("clean", d_clean), ("loss", d_loss), ("expl", d_expl),
                         ("peak", d_peak), ("resolve", d_res)):
                if v is not None:
                    deltas[sid][k].append(v)
    with open(os.path.join(OUT, "paired_results.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(pr[0].keys()))
        w.writeheader(); w.writerows(pr)
    # per-scale delta summary
    import random
    summ = {}
    for sid, d in deltas.items():
        row = {"scale": sid}
        for k, vals in d.items():
            if not vals:
                row[f"mean_delta_{k}"] = ""
                row[f"median_delta_{k}"] = ""
                row[f"bootstrap95_delta_{k}"] = ""
                continue
            vals = sorted(vals)
            mean = sum(vals) / len(vals)
            median = vals[len(vals) // 2]
            rng = random.Random(7)
            bmeans = []
            for _ in range(2000):
                sample = [rng.choice(vals) for _ in range(len(vals))]
                bmeans.append(sum(sample) / len(sample))
            bmeans.sort()
            row[f"mean_delta_{k}"] = round(mean, 3)
            row[f"median_delta_{k}"] = round(median, 3)
            row[f"bootstrap95_delta_{k}"] = f"[{bmeans[50]:.3f}, {bmeans[1950]:.3f}]"
        summ[sid] = row
    with open(os.path.join(OUT, "paired_summary.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(summ["S1"].keys()))
        w.writeheader()
        for sid in ("S1", "S2", "S3"):
            w.writerow(summ[sid])
    return pr, summ


def failure(rows):
    fc = [r for r in rows if r["clean_win"] != 1]
    cols = ["scenario", "profile", "seed", "result", "failure_type", "failure_reason",
            "friendly_usv_dead", "enemy_combat_killed", "enemy_alive_end",
            "breakthrough", "timeout", "peak_simultaneous_threat",
            "last_known_threat_count", "last_reliable_track_time", "global_reacquire_count"]
    with open(os.path.join(OUT, "failure_cases.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in fc:
            fr = r.get("failure_reason", "F_other")
            # map both prefixed (C_breakthrough) and bare (breakthrough) reasons
            m = {"breakthrough": "C", "lost_track_reacquire": "B", "resource_exhaustion": "D",
                 "runtime_error": "E", "timeout": "A", "throughput": "A"}.get(fr.split("_", 1)[-1], None)
            ft = m or (fr[0] if fr and fr[0] in "ABCDEF" else "F")
            w.writerow({
                "scenario": r["scenario"], "profile": PROF_LABELS.get(r["opponent_profile"], r["opponent_profile"]),
                "seed": r["seed"], "result": r["result"], "failure_type": ft,
                "failure_reason": fr, "friendly_usv_dead": r["friendly_usv_dead"],
                "enemy_combat_killed": r["enemy_combat_killed_event"],
                "enemy_alive_end": r["enemy_combat_alive_end"],
                "breakthrough": r["enemy_breakthrough_count"], "timeout": r["timeout"],
                "peak_simultaneous_threat": r["peak_simultaneous_threat_count"],
                "last_known_threat_count": r["enemy_combat_alive_end"],
                "last_reliable_track_time": "",
                "global_reacquire_count": r.get("global_reacquire_count"),
            })
    return fc


# ════════════════════════════════════════════════════════════════
def _style():
    plt.rcParams.update({"figure.facecolor": "white", "axes.facecolor": "white",
                         "savefig.facecolor": "white", "font.size": 11,
                         "axes.grid": True, "grid.alpha": 0.25})


def _pair(agg, sid, key):
    b0 = next(a for a in agg if a["scenario"] == sid and a["opponent_profile"] == "B0_RANDOM")
    b3 = next(a for a in agg if a["scenario"] == sid and a["opponent_profile"] == "B3_ADAPTIVE")
    return b0, b3


def figures(agg, pr):
    _style()
    xs = [0, 1, 2]
    labels = [SCEN_LABELS[s] for s in ("S1", "S2", "S3")]

    def grouped(key, ylab, title, fname, color=("#4472C4", "#C44E52")):
        plt.figure(figsize=(7, 4))
        W = 0.38
        v0 = [_f(next(a for a in agg if a["scenario"] == s and a["opponent_profile"] == "B0_RANDOM")[key]) or 0 for s in ("S1", "S2", "S3")]
        v3 = [_f(next(a for a in agg if a["scenario"] == s and a["opponent_profile"] == "B3_ADAPTIVE")[key]) or 0 for s in ("S1", "S2", "S3")]
        plt.bar([x - W / 2 for x in xs], v0, W, color="#4472C4", label="B0_RANDOM")
        plt.bar([x + W / 2 for x in xs], v3, W, color="#C44E52", label="B3_ADAPTIVE")
        plt.xticks(xs, labels); plt.ylabel(ylab); plt.title(f"{title} (N=30)")
        plt.legend(); plt.tight_layout()
        plt.savefig(os.path.join(FIG, fname), dpi=300); plt.close()

    # 01 clean win rate (3 groups, B0 vs B3, Wilson CI)
    plt.figure(figsize=(7, 4))
    b0v = [_f(next(a for a in agg if a["scenario"] == s and a["opponent_profile"] == "B0_RANDOM")["clean_win_rate"]) for s in ("S1", "S2", "S3")]
    b3v = [_f(next(a for a in agg if a["scenario"] == s and a["opponent_profile"] == "B3_ADAPTIVE")["clean_win_rate"]) for s in ("S1", "S2", "S3")]
    b0lo = [_f(next(a for a in agg if a["scenario"] == s and a["opponent_profile"] == "B0_RANDOM")["clean_win_ci95_low"]) for s in ("S1", "S2", "S3")]
    b0hi = [_f(next(a for a in agg if a["scenario"] == s and a["opponent_profile"] == "B0_RANDOM")["clean_win_ci95_high"]) for s in ("S1", "S2", "S3")]
    b3lo = [_f(next(a for a in agg if a["scenario"] == s and a["opponent_profile"] == "B3_ADAPTIVE")["clean_win_ci95_low"]) for s in ("S1", "S2", "S3")]
    b3hi = [_f(next(a for a in agg if a["scenario"] == s and a["opponent_profile"] == "B3_ADAPTIVE")["clean_win_ci95_high"]) for s in ("S1", "S2", "S3")]
    W = 0.38
    plt.figure(figsize=(7, 4))
    plt.bar([x - W / 2 for x in xs], b0v, W, yerr=[[a - b for a, b in zip(b0v, b0lo)], [a - b for a, b in zip(b0hi, b0v)]],
            capsize=4, color="#4472C4", label="B0_RANDOM")
    plt.bar([x + W / 2 for x in xs], b3v, W, yerr=[[a - b for a, b in zip(b3v, b3lo)], [a - b for a, b in zip(b3hi, b3v)]],
            capsize=4, color="#C44E52", label="B3_ADAPTIVE")
    plt.xticks(xs, labels); plt.ylabel("Clean Win Rate"); plt.title("Clean Win Rate: B0 vs B3 (N=30, Wilson 95% CI)")
    plt.ylim(0, 1.05); plt.legend(); plt.tight_layout()
    plt.savefig(os.path.join(FIG, "01_clean_win_b0_vs_b3.png"), dpi=300); plt.close()

    # 02-06 grouped bar pairs per scale
    grouped("avg_friendly_usv_dead", "Friendly USV Loss (mean)", "Friendly USV Loss", "02_friendly_usv_loss_b0_vs_b3.png")
    grouped("avg_enemy_combat_killed", "Enemy Combat Kills (mean)", "Enemy Combat Kills", "03_enemy_kills_b0_vs_b3.png")
    grouped("avg_explored_area_km2", "Explored Area (km², mean)", "Explored Area", "04_explored_area_b0_vs_b3.png")
    grouped("avg_peak_simultaneous_threat_count", "Peak Simultaneous Threats (mean)", "Peak Simultaneous Threats", "05_peak_simultaneous_threat_b0_vs_b3.png")
    grouped("avg_time_to_resolve", "Resolution Time (sim-s, mean)", "Combat Resolution Time", "06_resolution_time_b0_vs_b3.png")

    # 07 paired loss delta, 08 paired threat delta
    for fname, key in (("07_paired_loss_delta.png", "delta_friendly_usv_dead"),
                       ("08_paired_threat_delta.png", "delta_peak_simultaneous_threat")):
        plt.figure(figsize=(7, 4))
        xs2 = []
        ys2 = []
        cols = []
        off = 0
        for sid in ("S1", "S2", "S3"):
            for r in pr:
                if r["scale"] != sid:
                    continue
                v = _f(r[key])
                if v is None:
                    continue
                xs2.append(off); ys2.append(v)
                cols.append("#C44E52" if v > 0 else ("#4472C4" if v < 0 else "#888888"))
                off += 1
            off += 0.8
        plt.scatter(xs2, ys2, c=cols, s=18, alpha=0.7)
        plt.axhline(0, color="#333", lw=0.8)
        plt.xticks([], [])
        plt.xlabel("Seed (B3−B0, grouped by scale: S1 | S2 | S3)")
        plt.ylabel(f"{key} (B3−B0)")
        plt.title(f"Paired {key} per seed (N=30 per scale)")
        plt.tight_layout(); plt.savefig(os.path.join(FIG, fname), dpi=300); plt.close()


# ════════════════════════════════════════════════════════════════
def write_reports(agg, summ, failures, issues):
    main = []
    main.append("# Formal Opponent Evaluation — B0_RANDOM vs B3_ADAPTIVE\n")
    main.append("White frozen; simulator physics frozen; Black enhanced ONLY by legal "
                "observation-driven adaptive policy (B3). Paired seeds 1001–1030, N=30/setting.\n")
    main.append("## Main table\n")
    main.append("| Scale | Opponent | N | Clean Win | Enemy Kills | Friendly USV Loss | "
                "Explored Area | Peak Simult Threats | Resolution Time |")
    main.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for sid in ("S1", "S2", "S3"):
        for prof in ("B0_RANDOM", "B3_ADAPTIVE"):
            a = next(x for x in agg if x["scenario"] == sid and x["opponent_profile"] == prof)
            main.append(f"| {SCEN_LABELS[sid]} | {PROF_LABELS[prof]} | {a['N']} | {a['clean_wins']} | "
                        f"{a['avg_enemy_combat_killed']} | {a['avg_friendly_usv_dead']} | "
                        f"{a['avg_explored_area_km2']} | {a['avg_peak_simultaneous_threat_count']} | "
                        f"{a['avg_time_to_resolve']} |")
    main.append("")
    main.append("## Paired effect of adaptive opponent (Δ = B3 − B0)\n")
    main.append("| Scale | Δ Clean Win | Δ Friendly Loss | Δ Exploration | Δ Peak Threat | Δ Resolution Time |")
    main.append("|---|---:|---:|---:|---:|---:|")
    for sid in ("S1", "S2", "S3"):
        s = summ[sid]
        main.append(f"| {SCEN_LABELS[sid]} | {s['mean_delta_clean']} | {s['mean_delta_loss']} | "
                    f"{s['mean_delta_expl']} | {s['mean_delta_peak']} | {s['mean_delta_resolve']} |")
    main.append("")
    main.append("## Clean Win Rate (Wilson 95% CI)\n")
    for sid in ("S1", "S2", "S3"):
        for prof in ("B0_RANDOM", "B3_ADAPTIVE"):
            a = next(x for x in agg if x["scenario"] == sid and x["opponent_profile"] == prof)
            main.append(f"- {SCEN_LABELS[sid]} {PROF_LABELS[prof]}: {a['clean_wins']}/{a['N']} "
                        f"({a['clean_win_rate']:.3f}), CI [{a['clean_win_ci95_low']}, {a['clean_win_ci95_high']}]")
    main.append("")
    main.append("## Consistency check\n")
    main.append("\n".join(f"- {i}" for i in issues) if issues else "- All checks PASS (30/setting, 180 total).")
    main.append("")
    main.append("## Failures (non-clean)\n")
    if not failures:
        main.append("- None.")
    else:
        from collections import Counter
        c = Counter((r["scenario"], r["opponent_profile"], r["failure_reason"][0]) for r in failures)
        for k, v in sorted(c.items()):
            main.append(f"- {k[0]} {PROF_LABELS.get(k[1], k[1])}: type {k[2]} × {v}")
    main.append("")
    main.append("## B3 adaptive behavior (event counters)\n")
    for sid in ("S1", "S2", "S3"):
        rr = [r for r in failures if False]  # placeholder
    main.append("- See episode_results.csv b3_* columns (replan / lane-shift / dispersion / detection events).")
    main.append("")
    main.append("## Definitions\n")
    main.append("- clean_win = engine Victory (all enemy combat USV destroyed) AND breakthrough==0.")
    main.append("- enemy_combat_killed_event = event-based reconciled combat kill count (authoritative).")
    main.append("- peak_simultaneous_threat_count = max over White-legal steps of visible enemy count (same definition B0/B3).")
    main.append("- paired by initial scenario seed 1001–1030; trajectories may diverge after policy interaction.")
    with open(os.path.join(OUT, "FORMAL_OPPONENT_EVAL.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(main) + "\n")

    rep = ["# Formal Opponent Evaluation (B0 vs B3) — report\n", "## Setup\n",
           "- Frozen White (agent/skill/prompt/controllers), frozen simulator physics.",
           "- B0_RANDOM (random-waypoint baseline) vs B3_ADAPTIVE (legal observation-driven adaptive).",
           "- Scales: 5+5 vs10, 10+10 vs20, 15+15 vs30; N=30 each; 180 episodes; paired seeds 1001–1030.\n",
           "## Main results\n",
           "| Scale | Opponent | N | Clean Win | Enemy Kills | USV Loss | Explored km² | Peak Sim Threats | Resolve Time |",
           "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for sid in ("S1", "S2", "S3"):
        for prof in ("B0_RANDOM", "B3_ADAPTIVE"):
            a = next(x for x in agg if x["scenario"] == sid and x["opponent_profile"] == prof)
            rep.append(f"| {SCEN_LABELS[sid]} | {PROF_LABELS[prof]} | {a['N']} | {a['clean_wins']} | "
                       f"{a['avg_enemy_combat_killed']} | {a['avg_friendly_usv_dead']} | "
                       f"{a['avg_explored_area_km2']} | {a['avg_peak_simultaneous_threat_count']} | "
                       f"{a['avg_time_to_resolve']} |")
    rep.append("\n## Paired effect (Δ = B3−B0)\n")
    rep.append("| Scale | Δ Clean | Δ Loss | Δ Explored | Δ Peak Threat | Δ Resolve |")
    rep.append("|---|---:|---:|---:|---:|---:|")
    for sid in ("S1", "S2", "S3"):
        s = summ[sid]
        rep.append(f"| {SCEN_LABELS[sid]} | {s['mean_delta_clean']} | {s['mean_delta_loss']} | "
                   f"{s['mean_delta_expl']} | {s['mean_delta_peak']} | {s['mean_delta_resolve']} |")
    rep.append("\n## Key findings\n")
    rep.append("- See FORMAL_OPPONENT_EVAL.md and aggregate/paired CSVs for full numbers.")
    rep.append("- N=30 per setting; effect sizes + CI reported; no significance hacking.")
    with open(os.path.join(OUT, "FORMAL_OPPONENT_EVAL_FOR_REPORT.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(rep) + "\n")


def run():
    os.makedirs(FIG, exist_ok=True)
    rows = load_all()
    issues = sanity(rows)
    agg = aggregate(rows)
    pr, summ = paired(rows)
    failures = failure(rows)
    figures(agg, pr)
    write_reports(agg, summ, failures, issues)
    print("finalize done. issues:", issues if issues else "NONE")
    return issues


if __name__ == "__main__":
    run()
