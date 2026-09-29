#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""finalize_dev.py — DEV verdict, gates, S2 reproduction, figures, reports."""
import csv
import json
import os
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "c1_causal_dev")
FIG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "combat_exchange", "figures")
os.makedirs(FIG, exist_ok=True)
plt.rcParams["font.sans-serif"] = ["SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

rows = list(csv.DictReader(open(os.path.join(OUT, "DEV_EPISODES.csv"))))


def per(agent):
    p = defaultdict(lambda: [0, 0])
    for r in rows:
        if r["agent"] == agent:
            p[int(r["strategy"])][0] += int(r["black_kills"] or 0)
            p[int(r["strategy"])][1] += int(r["white_usv_losses"] or 0)
    return p


W5, C1 = per("W5"), per("C1")


def cer(k, l):
    return k / l if l else float("inf")


# per-strategy table
with open(os.path.join(OUT, "DEV_BY_STRATEGY.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["strategy", "W5_kills", "W5_losses", "W5_CER", "C1_kills", "C1_losses",
                "C1_CER", "CER_delta"])
    for sid in range(1, 7):
        wk, wl = W5[sid]; ck, cl = C1[sid]
        w.writerow([sid, wk, wl, round(cer(wk, wl), 3), ck, cl, round(cer(ck, cl), 3),
                    round(cer(ck, cl) - cer(wk, wl), 3)])

wk = sum(x[0] for x in W5.values()); wl = sum(x[1] for x in W5.values())
ck = sum(x[0] for x in C1.values()); cl = sum(x[1] for x in C1.values())
with open(os.path.join(OUT, "DEV_OVERALL.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["agent", "total_kills", "total_losses", "pooled_CER", "exchange_wins"])
    def wins(a):
        return sum(1 for r in rows if r["agent"] == a and int(r["black_kills"] or 0) > int(r["white_usv_losses"] or 0))
    w.writerow(["W5", wk, wl, round(cer(wk, wl), 4), f"{wins('W5')}/12"])
    w.writerow(["C1", ck, cl, round(cer(ck, cl), 4), f"{wins('C1')}/12"])

# gates
improved = sum(1 for sid in range(1, 7) if cer(C1[sid][0], C1[sid][1]) >= cer(W5[sid][0], W5[sid][1]))
g1 = cer(ck, cl) > cer(wk, wl)
g2 = ck >= 0.95 * wk
g3 = cl < wl
g4 = improved >= 4
s2_w = cer(W5[2][0], W5[2][1]); s2_c = cer(C1[2][0], C1[2][1])
g5 = not (s2_w > 1 and s2_c < 0.5)
g6 = s2_c > s2_w
print("GATES:")
print(f"G1 CER C1>W5: {g1} ({cer(ck,cl):.3f} vs {cer(wk,wl):.3f})")
print(f"G2 kills>=95%W5: {g2} ({ck} vs {0.95*wk:.1f})")
print(f"G3 losses reduced: {g3} ({cl} vs {wl})")
print(f"G4 >=4/6 improved: {g4} ({improved}/6)")
print(f"G5 no catastrophic S2: {g5} (W5 {s2_w:.2f}, C1 {s2_c:.2f})")
print(f"G6 S2 reproduced: {g6}")
verdict = "DEV_REVERSED" if cer(ck, cl) < cer(wk, wl) else ("DEV_FAIL" if not g2 else "DEV_WEAK_SUPPORT" if not g4 else "DEV_SUPPORTED")
print("VERDICT:", verdict)

# figures
labels = [f"S{i}" for i in range(1, 7)]
W5k = [W5[i][0] for i in range(1, 7)]; C1k = [C1[i][0] for i in range(1, 7)]
W5l = [W5[i][1] for i in range(1, 7)]; C1l = [C1[i][1] for i in range(1, 7)]
W5c = [cer(W5[i][0], W5[i][1]) for i in range(1, 7)]
C1c = [cer(C1[i][0], C1[i][1]) for i in range(1, 7)]
import numpy as np
x = np.arange(6); wd = 0.38

def grouped(y1, y2, ylab, title, fname):
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.bar(x - wd/2, y1, wd, label="W5", color="#d62728")
    ax.bar(x + wd/2, y2, wd, label="C1", color="#2ca02c")
    ax.set_xticks(x); ax.set_xticklabels(labels)
    ax.set_ylabel(ylab); ax.set_title(title); ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(FIG, fname), dpi=120); plt.close(fig)

grouped(W5k, C1k, "Black kills (N=2 pooled)", "FIG1 Black kills: W5 vs C1", "fig1_kills.png")
grouped(W5l, C1l, "White USV losses (N=2 pooled)", "FIG2 White losses: W5 vs C1", "fig2_losses.png")
grouped(W5c, C1c, "Pooled CER", "FIG3 Pooled CER: W5 vs C1", "fig3_cer.png")

fig, ax = plt.subplots(figsize=(7, 4))
ax.bar(["W5", "C1"], [wk, ck], color="#d62728", label="kills")
ax.bar(["W5", "C1"], [wl, cl], color="#2ca02c", label="losses", bottom=[wk, ck])
ax.set_title("FIG4 Overall: W5 vs C1 (24 episodes)"); ax.legend()
fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig4_overall.png"), dpi=120); plt.close(fig)

# S2 seed-level
s2_seeds = ["11001(hist)", "12101", "12102"]
s2_w = [0.0, 29/16, 28/14]; s2_c = [29/14, 4/19, 0.0]
fig, ax = plt.subplots(figsize=(7, 4))
x2 = np.arange(3)
ax.bar(x2 - wd/2, s2_w, wd, label="W5", color="#d62728")
ax.bar(x2 + wd/2, s2_c, wd, label="C1", color="#2ca02c")
ax.set_xticks(x2); ax.set_xticklabels(s2_seeds)
ax.set_ylabel("CER"); ax.set_title("FIG5 S2 reproduction: W5 vs C1")
ax.legend(); fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig5_s2.png"), dpi=120); plt.close(fig)

print("figures + CSVs written to", OUT, FIG)
