#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""build_master_tables.py — consolidate existing repo artifacts into machine-readable
master tables for the team sync pack. READ-ONLY: extracts only; never invents numbers.
Every row carries a `source` (file/DB) and `status`. Missing fields -> NOT_FOUND.
"""
import csv
import glob
import json
import os
import sqlite3
import statistics as st
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "docs", "team_sync", "data")
os.makedirs(OUT, exist_ok=True)
DB = os.path.join(ROOT, "strategy_library", "strategy_library.db")


def rd(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        return list(csv.DictReader(f))


def num(r, *keys):
    for k in keys:
        if k in r and r[k] not in (None, "", "None"):
            try:
                return float(r[k])
            except Exception:
                pass
    return None


def summarize(rows, loss_keys=("friendly_usv_dead", "friendly_total_dead", "friendly_usv_loss"),
              res_keys=("sim_time", "resolution_time", "resolution_time_s", "resolution"),
              brk_keys=("enemy_breakthrough_count", "breakthrough")):
    n = len(rows)
    if n == 0:
        return {"n": 0}
    def rate(pred):
        return round(sum(1 for r in rows if pred(r)) / n, 3)
    clean = rate(lambda r: r.get("clean_win") == "1")
    brk = rate(lambda r: (num(r, *brk_keys) or 0) > 0)
    def is_defeat(r):
        return "Defeat" in str(r.get("result", "")) or r.get("outcome") == "DEFEAT"
    def is_victory(r):
        return ("Victory" in str(r.get("result", ""))
                or r.get("outcome") in ("CLEAN_WIN", "BREAKTHROUGH_WIN"))
    defeat = rate(is_defeat)
    victory = rate(is_victory)
    loss = [num(r, *loss_keys) for r in rows if num(r, *loss_keys) is not None]
    res = [num(r, *res_keys) for r in rows if num(r, *res_keys) is not None]
    return {"n": n, "clean_rate": clean, "breakthrough_rate": brk, "defeat_rate": defeat,
            "victory_rate": victory,
            "loss_mean": round(st.mean(loss), 2) if loss else None,
            "resolution_mean": round(st.mean(res), 0) if res else None}


def main():
    registry = []
    white = []
    black = []

    def add(experiment_id, category, rows, white_policy, black_policy, scenario, seeds,
            status, result_file, report_file, notes, out):
        s = summarize(rows)
        rec = {"experiment_id": experiment_id, "category": category,
               "scenario": scenario, "white_policy": white_policy, "black_policy": black_policy,
               "seed_start": (min(seeds) if seeds else "NOT_FOUND"),
               "seed_end": (max(seeds) if seeds else "NOT_FOUND"),
               "requested_n": "NOT_FOUND", "valid_n": s.get("n", 0), "status": status,
               "victory_rate": s.get("victory_rate", "NOT_FOUND"),
               "clean_rate": s.get("clean_rate", "NOT_FOUND"),
               "breakthrough_rate": s.get("breakthrough_rate", "NOT_FOUND"),
               "defeat_rate": s.get("defeat_rate", "NOT_FOUND"),
               "loss_mean": s.get("loss_mean", "NOT_FOUND"),
               "resolution_mean": s.get("resolution_mean", "NOT_FOUND"),
               "result_file": result_file, "report_file": report_file, "notes": notes,
               "source": result_file}
        registry.append(rec)
        (white if category.startswith("white") else black).append(rec)

    # ---- formal_eval_20260825 (W5 vs B0) ----
    f = "formal_eval_20260825/episode_results.csv"
    rows = rd(os.path.join(ROOT, f))
    add("formal_eval_20260825", "white_vs_black", rows, "W5", "B0(black-b0-v1)", "S1/S2/S3",
        sorted(int(r["seed"]) for r in rows), "HISTORICAL", f,
        "formal_eval_20260825/FORMAL_EVAL_SUMMARY.md", "frozen W5 vs default B0", white)

    # ---- opponent_formal_eval (W5 vs B0/B3) ----
    f = "opponent_formal_eval/episode_results.csv"
    rows = rd(os.path.join(ROOT, f))
    for prof in sorted({r.get("opponent_profile") for r in rows}):
        sub = [r for r in rows if r.get("opponent_profile") == prof]
        add(f"opponent_formal_eval[{prof}]", "white_vs_black", sub, "W5", prof, "S1/S2/S3",
            sorted(int(r["seed"]) for r in sub), "HISTORICAL", f,
            "opponent_formal_eval/FORMAL_OPPONENT_EVAL.md", "W5 vs B0/B3 formal", black)

    # ---- auto_harness phase0 (W5 vs B3, N=100) ----
    f = "auto_harness/phase0/corpus/AUTO_HARNESS_EPISODES.csv"
    rows = rd(os.path.join(ROOT, f))
    add("auto_harness_phase0", "white_vs_black", rows, "W5", "B3_ADAPTIVE", "S2",
        sorted(int(r["seed"]) for r in rows), "COMPLETE", f,
        "auto_harness/phase0/analysis/AUTO_HARNESS_FAILURE_SUMMARY.md",
        "Phase0 discovery corpus; 35/35 non-clean have exactly 1 breakthrough", black)

    # ---- phase1 dev W5 / candidate ----
    for tag, sub, status, rep in (("w5", "auto_harness/phase1/dev_w5/EPISODES.csv", "COMPLETE",
                                   "auto_harness/phase1/ANTI_LEAK_DEV_REPORT.md"),
                                  ("cand", "auto_harness/phase1/dev_cand/EPISODES.csv", "PAUSED",
                                   "auto_harness/phase1/ANTI_LEAK_DEV_REPORT.md")):
        rows = rd(os.path.join(ROOT, sub))
        add(f"white_phase1_dev_{tag}", "white_candidate", rows,
            ("W5" if tag == "w5" else "white-auto-0001-v1"), "B3_ADAPTIVE", "S2",
            sorted(int(r["seed"]) for r in rows), status, sub, rep,
            "DEV paired 8001-8030 (candidate paused at valid_n)", white)

    # ---- common calibration (B0-B3) ----
    f = "policy_system/calibration/COMMON_CALIBRATION_EPISODES.csv"
    rows = rd(os.path.join(ROOT, f))
    for prof in sorted({r.get("opponent_profile") for r in rows}):
        sub = [r for r in rows if r.get("opponent_profile") == prof]
        add(f"common_calibration[{prof}]", "white_vs_black", sub, "W5", prof, "S2",
            sorted(int(r["seed"]) for r in sub), "COMPLETE", f,
            "policy_system/calibration/analysis/POLICY_B0_B3_COMMON_CALIBRATION_REPORT.md",
            "B0-B3 common calibration fp-v2", black)

    # ---- b0_v2 pilot/full ----
    for tag, sub in (("pilot", "b0_v2/pilot/EPISODES.csv"), ("full", "b0_v2/full/EPISODES.csv")):
        rows = rd(os.path.join(ROOT, sub))
        add(f"b0_v2_{tag}", "white_vs_black", rows, "W5", "black-b0-v2", "S2",
            sorted(int(r["seed"]) for r in rows), "COMPLETE", sub,
            "b0_v2/B0_V2_PILOT_REPORT.md" if tag == "pilot" else "b0_v2/B0_V2_FINGERPRINT_REPORT.md",
            "B0-v2 variable-speed baseline", black)

    # ---- auto_0001 (AUTO1) ----
    for tag, sub in (("s2", "policy_system/evolution/auto_0001/calibration_s2/EPISODES.csv"),
                     ("fresh", "policy_system/evolution/auto_0001/fresh_candidate/EPISODES.csv"),
                     ("cross_s1", "policy_system/evolution/auto_0001/cross_S1_candidate/EPISODES.csv"),
                     ("cross_s3", "policy_system/evolution/auto_0001/cross_S3_candidate/EPISODES.csv")):
        rows = rd(os.path.join(ROOT, sub))
        add(f"auto_0001_{tag}", "white_vs_black", rows, "W5", "black-auto-0001-v1",
            {"s2": "S2", "fresh": "S2", "cross_s1": "S1", "cross_s3": "S3"}[tag],
            sorted(int(r["seed"]) for r in rows), "COMPLETE", sub,
            "policy_system/evolution/auto_0001/AUTO_POLICY_ADMISSION_REPORT.md", "E3 candidate", black)

    # ---- w7 / w6 / coevolution (secondary) ----
    for eid, f, wp, bp in (("w7_performance_push", "w7_performance_push/W7_DEV_RESULTS.csv", "W5-variants", "B3?"),
                           ("coevolution_final", "coevolution_final/final_episode_results.csv", "W5/W6", "B0/B3"),
                           ("bt_regression_eval", "bt_regression_eval/integrated_results.csv", "W5/BT", "?")):
        rows = rd(os.path.join(ROOT, f))
        add(eid, "secondary", rows, wp, bp, "S1/S2/S3", [], "HISTORICAL", f,
            "NOT_FOUND", "secondary historical experiment", black)

    # ---- policy / artifact / fingerprint / validation tables from DB ----
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cards = {r["policy_id"]: dict(r) for r in con.execute("select * from policy_cards")}
    arts = {r["policy_id"]: dict(r) for r in con.execute("select * from policy_artifacts")}
    fps = list(con.execute("select policy_id,fingerprint_version,episode_count,scenario_set,seed_set from policy_fingerprints"))
    vals = list(con.execute("select candidate_policy_id,reference_policy_id,novelty_verdict,multi_seed_stable,empirical_distance from policy_validations"))
    con.close()

    with open(os.path.join(OUT, "master_policy_table.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["policy_id", "side", "strategy_family", "status", "evaluation_role",
                    "parent_policy_id", "bundle_hash", "entrypoint", "artifact_hash",
                    "fp_versions", "fp_episodes", "source"])
        for pid, c in sorted(cards.items()):
            a = arts.get(pid, {})
            fpl = [f"{r['fingerprint_version']}:{r['episode_count']}" for r in fps if r["policy_id"] == pid]
            w.writerow([pid, c.get("side"), c.get("strategy_family"), c.get("status"),
                        c.get("evaluation_role"), c.get("parent_policy_id"),
                        a.get("bundle_hash"), a.get("entrypoint"), a.get("artifact_hash"),
                        ";".join(fpl), "", "strategy_library.db"])

    with open(os.path.join(OUT, "master_artifact_registry.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["policy_id", "entrypoint", "artifact_hash", "bundle_hash", "config_hash",
                    "environment_hash", "simulator_hash", "opponent_module_hash", "git_commit", "source"])
        for pid, a in sorted(arts.items()):
            w.writerow([pid, a.get("entrypoint"), a.get("artifact_hash"), a.get("bundle_hash"),
                        a.get("config_hash"), a.get("environment_hash"), a.get("simulator_hash"),
                        a.get("opponent_module_hash"), a.get("git_commit"), "strategy_library.db"])

    with open(os.path.join(OUT, "master_experiment_registry.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(registry[0].keys()))
        w.writeheader()
        for r in registry:
            w.writerow(r)

    def dump(name, rows_):
        if not rows_:
            open(os.path.join(OUT, name), "w").write("experiment_id,note\n")
            return
        keys = ["experiment_id", "category", "scenario", "white_policy", "black_policy",
                "seed_start", "seed_end", "valid_n", "status", "clean_rate", "breakthrough_rate",
                "defeat_rate", "loss_mean", "resolution_mean", "result_file", "source"]
        with open(os.path.join(OUT, name), "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
            w.writeheader()
            for r in rows_:
                w.writerow(r)
    dump("master_white_results.csv", white)
    dump("master_black_results.csv", black)

    with open(os.path.join(OUT, "master_match_winrate.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["experiment_id", "white_policy", "black_policy", "scenario",
                    "seed_start", "seed_end", "valid_n", "white_victory_rate", "white_clean_rate",
                    "black_win_rate(breakthrough)", "white_defeat_rate", "source"])
        for r in registry:
            w.writerow([r["experiment_id"], r["white_policy"], r["black_policy"], r["scenario"],
                        r["seed_start"], r["seed_end"], r["valid_n"], r.get("victory_rate"),
                        r.get("clean_rate"), r.get("breakthrough_rate"), r.get("defeat_rate"),
                        r["result_file"]])

    with open(os.path.join(OUT, "master_open_experiments.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["item", "status", "detail", "source"])
        w.writerow(["white_phase1_dev_candidate", "PAUSED",
                    "dev_cand valid_n=%d/30 (8001-8030)" % len(rd(os.path.join(ROOT, 'auto_harness/phase1/dev_cand/EPISODES.csv'))),
                    "auto_harness/phase1/dev_cand/EPISODES.csv"])
        w.writerow(["anti_leak_fresh_validation", "PENDING", "8101-8130 not started", "NOT_FOUND"])
        w.writerow(["anti_leak_cross_opponent", "PENDING", "8201-8210 not started", "NOT_FOUND"])
        w.writerow(["b0_v2_27class_official", "COMPLETE", "N=27 seeds 9001-9027", "b0_v2/B0_V2_27CLASS_COUNTS.csv"])
        w.writerow(["b0_v2_full_review", "COMPLETE", "N=90 seeds 9001-9090", "b0_v2/n90_review/"])
        w.writerow(["auto1_response_trigger", "OPEN", "response trigger fired 0/10; timeout fallback only",
                    "policy_system/evolution/auto_0001/calibration_s2/traces/*_autoevents.json"])
        w.writerow(["e1_b1_vs_b2", "INCONCLUSIVE", "behavior distance 0.371", "policy_system/calibration/analysis/POLICY_DIFFERENCE_MATRIX_V2.csv"])

    print("registry rows:", len(registry))
    print("white rows:", len(white), "black rows:", len(black))
    print("wrote to", OUT)


if __name__ == "__main__":
    main()
