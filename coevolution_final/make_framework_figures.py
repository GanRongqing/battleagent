#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""coevolution_final/make_framework_figures.py — thesis framework diagrams.

figure_coevolution_framework.png      : 8-step Evidence-Driven Alternating Adversarial
                                        Co-Evolution loop (grayscale, 300 dpi).
figure_current_evolution_instance.png : concrete W5xB0 -> W5xB3 -> W6xB3 instantiation.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch  # noqa: E402

OUT = __import__("os").path.dirname(__import__("os").path.abspath(__file__))
FIG = __import__("os").path.join(OUT, "figures")


def _box(ax, xy, w, h, text, fc="white", ec="black", fontsize=9, weight="normal"):
    x, y = xy
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.02",
                       fc=fc, ec=ec, lw=1.3)
    ax.add_patch(p)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fontsize, fontweight=weight, wrap=True)


def _arrow(ax, p1, p2, style="-|>"):
    a = FancyArrowPatch(p1, p2, arrowstyle=style, mutation_scale=16, lw=1.4, color="black")
    ax.add_patch(a)


def framework():
    fig, ax = plt.subplots(figsize=(7.2, 9.2), dpi=300)
    ax.set_xlim(0, 10); ax.set_ylim(0, 13)
    ax.axis("off")
    bw, bh = 6.6, 1.05
    cx = 1.7
    boxes = [
        (cx, 11.6, "STEP 1 — BASELINE FREEZE\nFreeze W_t, B_t, Skill, Prompt, Physics\n(hash/config/seed recorded)"),
        (cx, 9.8, "STEP 2 — ONE-SIDED ADVERSARY EVOLUTION\nB_t -> B_{t+1}   (legal observation only,\nno physics buff, no hidden state, no seed hardcode)"),
        (cx, 8.0, "STEP 3 — ADVERSARIAL EVALUATION\nE(W_t, B_t)  vs  E(W_t, B_{t+1})\n(outcome / search & resource burden / delay / breakthrough)"),
        (cx, 6.2, "STEP 4 — EVIDENCE EXTRACTION & DIAGNOSIS\ntrace / audit / failure cases / paired runs\n-> failure mode + root cause"),
        (cx, 4.4, "STEP 5 — CONTROLLED WHITE ADAPTATION\nB_{t+1} frozen;  W_t -> W_{t+1}\nlayer explicit (Skill / Harness / Controller / Belief)"),
        (cx, 2.6, "STEP 6 — MECHANISM VALIDATION\nunit / fair-play / counterfactual / paired traces /\nablation / regression"),
        (cx, 0.8, "STEP 7 — HOLDOUT VALIDATION\nW_{t+1} frozen; unseen seeds\nE(W_t, B_{t+1}) vs E(W_{t+1}, B_{t+1})"),
    ]
    _box(ax, (1.7, 0.05), 6.6, 0.55,
         "STEP 8 — RELEASE & ROLE SWAP: freeze W_{t+1}; next round B_{t+1} -> B_{t+2}",
         fontsize=8.5, weight="bold", ec="black")
    for i, (x, y, t) in enumerate(boxes):
        _box(ax, (x, y), bw, bh, t, fontsize=9)
        if i + 1 < len(boxes):
            _arrow(ax, (x + bw / 2, y - 0.02), (x + bw / 2, boxes[i + 1][1] + bh + 0.02))
    # release box -> back to top (loop) + role-swap to next round
    _arrow(ax, (1.7 + bw / 2, 0.6), (1.7 + bw / 2, 11.6 + bh + 0.5), style="-|>")
    ax.text(1.7 + bw / 2 + 0.35, 6.0, "round t+1", rotation=90, fontsize=8,
            va="center", style="italic")
    ax.set_title("Evidence-Driven Alternating Adversarial Co-Evolution\n"
                 "(frozen-checkpoint alternation: one side evolves per round)",
                 fontsize=11)
    fig.tight_layout()
    fig.savefig(__import__("os").path.join(FIG, "figure_coevolution_framework.png"), dpi=300)
    plt.close(fig)
    print("wrote figure_coevolution_framework.png")


def instance():
    fig, ax = plt.subplots(figsize=(7.2, 6.4), dpi=300)
    ax.set_xlim(0, 10); ax.set_ylim(0, 10)
    ax.axis("off")
    _box(ax, (0.9, 8.2), 8.2, 1.1, "STAGE 0 — Initial Baseline\nWhite W5 (frozen)  x  Black B0_RANDOM\nclean baseline", fontsize=9.5)
    _box(ax, (0.9, 6.0), 8.2, 1.1, "STAGE 1 — Black Evolved\nWhite W5 (frozen)  x  Black B3_ADAPTIVE\nlegal-observation replanning / lane shift / dispersion / adaptive penetration", fontsize=9.5)
    _box(ax, (0.9, 3.8), 8.2, 1.1, "STAGE 2 — White Adapted\nWhite W6 (anti-evasion)  x  Black B3 (frozen)\npredictive intercept / pursuit-cost allocation / handoff /\nUAV track maintenance / adaptive screen / breakthrough-horizon risk", fontsize=9)
    _arrow(ax, (5.0, 8.2), (5.0, 7.12))
    ax.text(5.15, 7.6, "Black evolution (B_t -> B_{t+1})", fontsize=8, rotation=90, style="italic")
    _arrow(ax, (5.0, 6.0), (5.0, 4.92))
    ax.text(5.15, 5.4, "White anti-evasion adaptation\nover frozen B3 (W_t -> W_{t+1})", fontsize=8,
            style="italic", ha="center")
    # failure evidence annotations
    ax.text(9.35, 6.5, "failure evidence:\n+ exploration burden\n+ resolution delay\n+ breakthrough pressure",
            fontsize=7.5, ha="center", va="center",
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="black", lw=0.8))
    ax.set_title("Current Project Instantiation of the Framework", fontsize=11)
    fig.tight_layout()
    fig.savefig(__import__("os").path.join(FIG, "figure_current_evolution_instance.png"), dpi=300)
    plt.close(fig)
    print("wrote figure_current_evolution_instance.png")


if __name__ == "__main__":
    framework()
    instance()
