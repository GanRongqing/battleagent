#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""c4_figs.py — Stage B figures (FIG1..FIG6)."""
import csv
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(ROOT, "auto_harness", "combat_exchange", "c4_reachability_weighted_commitment")
FIG = os.path.join(BASE, "fresh_eval", "figures")
os.makedirs(FIG, exist_ok=True)


def rows(name):
    with open(os.path.join(BASE, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def num(x):
    try:
        return float(x)
    except Exception:
        return np.nan


summ = rows("04_COMBAT_SUMMARY.csv")
pair = rows("05_PAIRED_SEED_COMPARISON.csv")
mech = rows("02_MECHANISM_METRICS.csv")


def cell(rs, pol, strat, key):
    for r in rs:
        if r["policy"] == pol and r["strategy"] == strat:
            return r[key]
    return None


# FIG1 pooled CER
fig, ax = plt.subplots(figsize=(6, 4))
labels = ["ACE", "C4"]
vals = [float(cell(summ, "ACE", "OVERALL", "pooled_CER")), float(cell(summ, "C4", "OVERALL", "pooled_CER"))]
ax.bar(labels, vals, color=["#1f77b4", "#2ca02c"])
for i, v in enumerate(vals):
    ax.text(i, v, f"{v:.3f}", ha="center", va="bottom")
ax.set_ylabel("pooled CER"); ax.set_title("FIG1 Pooled CER: ACE vs C4 (all valid)")
fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig1_pooled_cer.png"), dpi=110); plt.close(fig)

# FIG2 kills / losses
fig, ax = plt.subplots(figsize=(7, 4)); x = np.arange(2); w = 0.35
ak = [float(cell(summ, "ACE", "OVERALL", "kills")), float(cell(summ, "C4", "OVERALL", "kills"))]
al = [float(cell(summ, "ACE", "OVERALL", "losses")), float(cell(summ, "C4", "OVERALL", "losses"))]
ax.bar(x - w / 2, ak, w, label="kills", color="#2ca02c")
ax.bar(x + w / 2, al, w, label="white losses", color="#d62728")
ax.set_xticks(x); ax.set_xticklabels(labels); ax.legend()
ax.set_title("FIG2 Kills / White Losses (all valid)")
fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig2_kills_losses.png"), dpi=110); plt.close(fig)

# FIG3 mechanism proxies
fig, ax = plt.subplots(figsize=(7, 4)); x = np.arange(3); w = 0.35
keys = ["mean_coverage_frac", "mean_max_lock", "mean_max_engaged"]
av = [num(next(r for r in mech if r["policy"] == "ACE")[k]) for k in keys]
cv = [num(next(r for r in mech if r["policy"] == "C4")[k]) for k in keys]
ax.bar(x - w / 2, av, w, label="ACE", color="#1f77b4")
ax.bar(x + w / 2, cv, w, label="C4", color="#2ca02c")
ax.set_xticks(x); ax.set_xticklabels(["coverage_frac", "max_lock", "max_engaged"]); ax.legend()
ax.set_title("FIG3 Mechanism proxies: ACE vs C4")
fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig3_mechanism.png"), dpi=110); plt.close(fig)

# FIG4 death-before-lock eps
fig, ax = plt.subplots(figsize=(6, 4))
av = float(next(r for r in mech if r["policy"] == "ACE")["death_before_lock_eps"])
cv = float(next(r for r in mech if r["policy"] == "C4")["death_before_lock_eps"])
ax.bar(labels, [av, cv], color=["#1f77b4", "#2ca02c"])
ax.set_ylabel("episodes"); ax.set_title("FIG4 Death-before-own-lock (episodes)")
fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig4_death_before_lock.png"), dpi=110); plt.close(fig)

# FIG5 assigned->lock proxy (max_lock)
fig, ax = plt.subplots(figsize=(6, 4))
av = float(next(r for r in mech if r["policy"] == "ACE")["mean_max_lock"])
cv = float(next(r for r in mech if r["policy"] == "C4")["mean_max_lock"])
ax.bar(labels, [av, cv], color=["#1f77b4", "#2ca02c"])
ax.set_ylabel("mean max simultaneous locks"); ax.set_title("FIG5 Assigned->Lock proxy")
fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig5_assigned_lock.png"), dpi=110); plt.close(fig)

# FIG6 per-seed paired combat (dK, dL)
fig, ax = plt.subplots(figsize=(8, 4))
xs = [f"{r['strategy']}/s{r['seed']}" for r in pair]
dk = [num(r["dK"]) for r in pair]; dl = [num(r["dL"]) for r in pair]
x = np.arange(len(xs)); w = 0.4
ax.bar(x - w / 2, dk, w, label="dKills (C4-ACE)", color="#2ca02c")
ax.bar(x + w / 2, dl, w, label="dLosses (C4-ACE)", color="#d62728")
ax.axhline(0, color="k", lw=0.8)
ax.set_xticks(x); ax.set_xticklabels(xs, rotation=45, ha="right"); ax.legend()
ax.set_title("FIG6 Per-seed paired combat delta (C4 - ACE)")
fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig6_paired_delta.png"), dpi=110); plt.close(fig)
print("figures written to", FIG)
