#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""c4_analyze.py — Stage B analysis: combat + mechanism metrics from the episode logs.

Inputs : auto_harness/combat_exchange/c4_reachability_weighted_commitment/fresh_eval/raw/*/*.log
Outputs: 01_EPISODE_RESULTS.csv, 02_MECHANISM_METRICS.csv, 03_REACHABILITY_BINS.csv,
         04_COMBAT_SUMMARY.csv, 05_PAIRED_SEED_COMPARISON.csv
"""
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(ROOT, "auto_harness", "combat_exchange", "c4_reachability_weighted_commitment")
RAW = os.path.join(BASE, "fresh_eval", "raw")
SUM = os.path.join(BASE, "fresh_eval", "summaries")
os.makedirs(SUM, exist_ok=True)
POL = {"expand": "ACE", "reach": "C4"}
STRAT = {"s1": "S1", "s6": "S6"}
STEP_RE = re.compile(r"^\[t=([\d,]+)s\] step=(\d+) \|.*?USV: (\d+)/(\d+) \(avail=(\d+) int=(\d+) lock=(\d+) frz=(\d+)\).*?"
                     r"TRACKS: vis=(\d+) lost=(\d+) engaged=(\d+) \|.*?KILL=(\d+)")


def parse(logf):
    txt = open(logf, encoding="utf-8", errors="replace").read()
    meta = {}
    for k in ("enemy_kills", "friendly_usv_losses", "friendly_uav_losses", "black_breakthrough",
              "first_detection", "first_lock", "first_kill", "victory_time"):
        m = re.search(rf"\b{k}=(\S+)", txt)
        meta[k] = m.group(1) if m else None
    m = re.search(r"\[META\] result=(\S+)", txt)
    meta["result"] = m.group(1) if m else None
    steps = []
    for line in txt.splitlines():
        mm = STEP_RE.match(line)
        if mm:
            g = mm.groups()
            steps.append({"t": int(g[0].replace(",", "")), "step": int(g[1]),
                          "usv_alive": int(g[2]), "usv_total": int(g[3]), "avail": int(g[4]),
                          "inter": int(g[5]), "lock": int(g[6]), "frz": int(g[7]),
                          "vis": int(g[8]), "lost": int(g[9]), "engaged": int(g[10]),
                          "kill": int(g[11])})
    return meta, steps, txt


def main():
    eps = []
    for logf in sorted(glob.glob(os.path.join(RAW, "*", "*.log"))):
        fname = os.path.basename(logf)
        m = re.match(r"(s\d)_(expand|reach)_(S\d)_seed(\d+)\.log", fname)
        if not m:
            continue
        strat = m.group(3); pol = POL[m.group(2)]; seed = int(m.group(4))
        meta, steps, txt = parse(logf)
        valid = "[META]" in txt
        kills = int(meta["enemy_kills"]) if meta.get("enemy_kills") else 0
        losses = int(meta["friendly_usv_losses"]) if meta.get("friendly_usv_losses") else 0
        engaged_steps = sum(1 for s in steps if s["engaged"] > 0)
        lock_steps = sum(1 for s in steps if s["lock"] > 0)
        max_engaged = max([s["engaged"] for s in steps], default=0)
        max_lock = max([s["lock"] for s in steps], default=0)
        # mechanism proxies
        # coverage proxy: fraction of steps with >=1 engaged track
        cov = round(engaged_steps / len(steps), 3) if steps else None
        # death-before-own-lock proxy: episodes where losses occurred while max_lock==0
        dbl = 1 if (losses > 0 and max_lock == 0) else 0
        eps.append({"policy": pol, "strategy": strat, "seed": seed, "valid": valid,
                    "enemy_kills": kills, "white_usv_losses": losses,
                    "CER": (round(kills / losses, 3) if losses else ("K:0" if kills == 0 else "INF")),
                    "result": meta.get("result"), "n_steps": len(steps),
                    "max_engaged": max_engaged, "max_lock": max_lock,
                    "coverage_frac": cov, "death_before_lock_flag": dbl,
                    "first_detection": meta.get("first_detection"), "first_lock": meta.get("first_lock"),
                    "first_kill": meta.get("first_kill"), "logfile": logf})
    # 01 episode results
    import csv
    if eps:
        with open(os.path.join(BASE, "fresh_eval", "01_EPISODE_RESULTS.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(eps[0].keys())); w.writeheader(); w.writerows(eps)
    # valid only for combat aggregation
    val = [e for e in eps if e["valid"]]
    # 04 combat summary: pooled per policy / strategy
    def pooled(rows):
        k = sum(r["enemy_kills"] for r in rows); l = sum(r["white_usv_losses"] for r in rows)
        return k, l, (round(k / l, 3) if l else ("INF" if k else "0"))
    summ = []
    for pol in ("ACE", "C4"):
        for strat in ("S1", "S6"):
            rows = [e for e in val if e["policy"] == pol and e["strategy"] == strat]
            k, l, cer = pooled(rows)
            summ.append({"policy": pol, "strategy": strat, "n_valid": len(rows),
                         "kills": k, "losses": l, "pooled_CER": cer})
        rows = [e for e in val if e["policy"] == pol]
        k, l, cer = pooled(rows)
        summ.append({"policy": pol, "strategy": "OVERALL", "n_valid": len(rows),
                     "kills": k, "losses": l, "pooled_CER": cer})
    with open(os.path.join(BASE, "04_COMBAT_SUMMARY.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(summ[0].keys())); w.writeheader(); w.writerows(summ)
    # 05 paired seed comparison
    paired = []
    for seed in sorted({e["seed"] for e in val}):
        for strat in ("S1", "S6"):
            a = next((e for e in val if e["policy"] == "ACE" and e["strategy"] == strat and e["seed"] == seed), None)
            c = next((e for e in val if e["policy"] == "C4" and e["strategy"] == strat and e["seed"] == seed), None)
            paired.append({"strategy": strat, "seed": seed,
                           "ACE_k": a["enemy_kills"] if a else None, "ACE_l": a["white_usv_losses"] if a else None,
                           "C4_k": c["enemy_kills"] if c else None, "C4_l": c["white_usv_losses"] if c else None,
                           "dK": (c["enemy_kills"] - a["enemy_kills"]) if a and c else None,
                           "dL": (c["white_usv_losses"] - a["white_usv_losses"]) if a and c else None})
    with open(os.path.join(BASE, "05_PAIRED_SEED_COMPARISON.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(paired[0].keys())); w.writeheader(); w.writerows(paired)
    # 02 mechanism metrics (proxies)
    mech = []
    for pol in ("ACE", "C4"):
        rows = [e for e in val if e["policy"] == pol]
        if not rows:
            continue
        mech.append({"policy": pol, "n": len(rows),
                     "mean_coverage_frac": round(sum(r["coverage_frac"] for r in rows) / len(rows), 3),
                     "mean_max_lock": round(sum(r["max_lock"] for r in rows) / len(rows), 2),
                     "mean_max_engaged": round(sum(r["max_engaged"] for r in rows) / len(rows), 2),
                     "death_before_lock_eps": sum(r["death_before_lock_flag"] for r in rows)})
    with open(os.path.join(BASE, "02_MECHANISM_METRICS.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(mech[0].keys())); w.writeheader(); w.writerows(mech)
    print(json.dumps({"n_episodes": len(eps), "n_valid": len(val), "summary": summ, "mech": mech},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
