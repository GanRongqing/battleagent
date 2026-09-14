#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""analyze_phase1.py — paired W5 vs candidate DEV/FRESH analysis + causal verdict."""
import csv
import json
import math
import os
import statistics as st
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "auto_harness", "phase1")


def load(path):
    if not os.path.exists(path):
        return {}
    return {int(r["seed"]): r for r in csv.DictReader(open(path))}


def wilson(k, n, z=1.96):
    if n == 0:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(max(0, c - h), 3), round(min(1, c + h), 3))


def num(r, k):
    try:
        return float(r[k]) if r.get(k) not in (None, "", "None") else None
    except Exception:
        return None


def summarize(group):
    n = len(group)
    clean = sum(1 for r in group if r.get("clean_win") == "1")
    brk = sum(1 for r in group if num(r, "enemy_breakthrough_count") and num(r, "enemy_breakthrough_count") > 0)
    defeat = sum(1 for r in group if r.get("result") == "Result.Defeat")
    loss = st.mean([num(r, "friendly_usv_dead") or 0 for r in group]) if group else None
    res = st.mean([num(r, "sim_time") or 0 for r in group]) if group else None
    return {"n": n, "clean": clean, "clean_rate": round(clean / n, 3) if n else None,
            "clean_ci": wilson(clean, n),
            "breakthrough": brk, "breakthrough_rate": round(brk / n, 3) if n else None,
            "breakthrough_ci": wilson(brk, n),
            "defeat": defeat, "defeat_rate": round(defeat / n, 3) if n else None,
            "defeat_ci": wilson(defeat, n),
            "friendly_loss_mean": round(loss, 2) if loss is not None else None,
            "resolution_mean": round(res, 1) if res is not None else None}


def run(dev_w5, dev_cand, tag="DEV", out_prefix="ANTI_LEAK_DEV", cand_events_glob="*_w8events.json"):
    w5 = load(os.path.join(dev_w5, "EPISODES.csv"))
    cd = load(os.path.join(dev_cand, "EPISODES.csv"))
    seeds = sorted(set(w5) & set(cd))
    sw5 = summarize([w5[s] for s in seeds])
    scd = summarize([cd[s] for s in seeds])
    # paired transitions on breakthrough
    trans = {"w5_fail_cand_clean": 0, "w5_clean_cand_fail": 0, "both_clean": 0, "both_fail": 0}
    for s in seeds:
        a = num(w5[s], "enemy_breakthrough_count") > 0
        b = num(cd[s], "enemy_breakthrough_count") > 0
        if a and not b:
            trans["w5_fail_cand_clean"] += 1
        elif not a and b:
            trans["w5_clean_cand_fail"] += 1
        elif not a and not b:
            trans["both_clean"] += 1
        else:
            trans["both_fail"] += 1
    # mechanism events
    import glob
    evs = [json.load(open(p)) for p in glob.glob(os.path.join(dev_cand, cand_events_glob))]
    mech = {}
    if evs:
        mech = {"episodes_with_events": len(evs),
                "containment_triggers_mean": round(st.mean(e.get("containment_triggered", 0) for e in evs), 2),
                "containment_triggers_total": sum(e.get("containment_triggered", 0) for e in evs),
                "preemptions_total": sum(e.get("preemptions", 0) for e in evs),
                "episodes_with_trigger": sum(1 for e in evs if e.get("containment_triggered", 0) > 0),
                "unblocked_high_evals_total": sum(e.get("unblocked_high_risk_evals", 0) for e in evs),
                "unblocked_critical_evals_total": sum(e.get("unblocked_critical_risk_evals", 0) for e in evs)}
    bd = (scd["breakthrough_rate"] or 0) - (sw5["breakthrough_rate"] or 0)
    if sw5["n"] < 10:
        causal = "INSUFFICIENT_N"
    elif mech.get("containment_triggers_total", 0) == 0:
        causal = "MECHANISM_NOT_FIRING"
    elif bd >= -0.02:
        causal = "HYPOTHESIS_NOT_SUPPORTED"
    elif (scd["friendly_loss_mean"] or 0) > (sw5["friendly_loss_mean"] or 0) * 1.15 or \
            (scd["defeat_rate"] or 0) > (sw5["defeat_rate"] or 0) + 0.05:
        causal = "BAD_TRADEOFF"
    else:
        causal = "SUPPORTED"
    report = {"tag": tag, "seeds": seeds, "n_paired": len(seeds),
              "w5": sw5, "candidate": scd, "breakthrough_delta": round(bd, 3),
              "transitions": trans, "mechanism": mech, "causal_verdict": causal}
    json.dump(report, open(os.path.join(OUT, f"{out_prefix}_SUMMARY.json"), "w"), indent=2)
    with open(os.path.join(OUT, f"{out_prefix}_RESULTS.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["seed", "w5_breakthrough", "cand_breakthrough", "w5_clean", "cand_clean",
                    "w5_loss", "cand_loss", "w5_resolution", "cand_resolution"])
        for s in seeds:
            w.writerow([s, int(num(w5[s], "enemy_breakthrough_count") > 0),
                        int(num(cd[s], "enemy_breakthrough_count") > 0),
                        w5[s].get("clean_win"), cd[s].get("clean_win"),
                        num(w5[s], "friendly_usv_dead"), num(cd[s], "friendly_usv_dead"),
                        num(w5[s], "sim_time"), num(cd[s], "sim_time")])
    lines = [f"# Anti-Leak {tag} Results (paired, S2 x B3)", "",
             f"- paired N = {len(seeds)}", "",
             "| metric | W5 | candidate |", "|---|---|---|",
             f"| clean rate | {sw5['clean_rate']} (CI {sw5['clean_ci']}) | {scd['clean_rate']} (CI {scd['clean_ci']}) |",
             f"| breakthrough rate | {sw5['breakthrough_rate']} (CI {sw5['breakthrough_ci']}) | {scd['breakthrough_rate']} (CI {scd['breakthrough_ci']}) |",
             f"| defeat rate | {sw5['defeat_rate']} (CI {sw5['defeat_ci']}) | {scd['defeat_rate']} (CI {scd['defeat_ci']}) |",
             f"| friendly loss mean | {sw5['friendly_loss_mean']} | {scd['friendly_loss_mean']} |",
             f"| resolution mean | {sw5['resolution_mean']} | {scd['resolution_mean']} |", "",
             f"- breakthrough delta (cand - W5) = {round(bd,3)}", "",
             f"## Paired transitions (breakthrough)", "",
             f"- W5 fail -> candidate clean: {trans['w5_fail_cand_clean']}",
             f"- W5 clean -> candidate fail: {trans['w5_clean_cand_fail']}",
             f"- both clean: {trans['both_clean']}", f"- both fail: {trans['both_fail']}", "",
             f"## Mechanism KPIs", "", f"```\n{json.dumps(mech, indent=2)}\n```", "",
             f"## Causal verdict = **{causal}**", ""]
    open(os.path.join(OUT, f"{out_prefix}_REPORT.md"), "w").write("\n".join(lines))
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    run(os.path.join(OUT, "dev_w5"), os.path.join(OUT, "dev_cand"), "DEV", "ANTI_LEAK_DEV")
