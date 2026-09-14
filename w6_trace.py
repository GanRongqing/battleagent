#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""w6_trace.py — W6 paired failure trace audit (STEP 1, read-only).

Builds per-step traces for a W5 vs W6 paired case from the API game logs + agent logs,
finds the FIRST CAUSAL DIVERGENCE (not final outcome), and writes trace markdown.
Uses only legal /status data (usv positions, locking, active_enemies).

Usage: python w6_trace.py --w5 <game_log> --w6 <game_log> --out <md>
"""
import argparse
import json
import math
import os
import sys


def load_game(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def build_series(game, n_usv=5):
    """Per-step: sim_time, per-USV {position, dist_to_nearest_enemy, locking},
    alive USV count, active enemy positions."""
    series = []
    for s in game.get("steps", []):
        t = float(s.get("sim_time", 0))
        usvs = s.get("usv_states", []) or []
        enemies = [tuple(e.get("position", [0, 0, 0])[:2])
                   for e in (s.get("active_enemies", []) or [])
                   if e.get("position")]
        usv_info = {}
        for u in usvs:
            name = u.get("name")
            pos = tuple(u.get("position", [0, 0, 0])[:2]) if u.get("position") else None
            if name is None:
                continue
            d = min((_dist(pos, e) for e in enemies), default=None) if pos and enemies else None
            usv_info[name] = {"pos": pos, "dist": d,
                              "locking": bool(u.get("is_locking")),
                              "locking_unit": u.get("locking_unit"),
                              "frozen": bool(u.get("is_frozen")),
                              "alive": bool(u.get("is_alive", True))}
        alive = sum(1 for v in usv_info.values() if v["alive"])
        series.append({"t": t, "usvs": usv_info, "alive": alive, "n_enemy": len(enemies),
                       "enemies": enemies})
    return series


def nearest_series(a, t, key="dist"):
    """interpolate value from series a at time t (nearest step)."""
    best = None
    for s in a:
        if abs(s["t"] - t) < 1e-6:
            return s
        if best is None or abs(s["t"] - t) < abs(best["t"] - t):
            best = s
    return best


def first_divergence(w5, w6):
    """Find first sim_time where a significant decision differs.

    Divergence signals (first one wins):
      1. alive USV count differs
      2. a USV is locking in one but not the other
      3. a USV's distance-to-nearest-enemy differs by > 5000 m
    """
    events = []
    for s6 in w6:
        t = s6["t"]
        s5 = nearest_series(w5, t)
        if s5 is None:
            continue
        # 1. alive count
        if s6["alive"] != s5["alive"]:
            return t, "alive_count", s5, s6
        names = set(s5["usvs"]) & set(s6["usvs"])
        for n in names:
            a, b = s5["usvs"][n], s6["usvs"][n]
            # 2. locking divergence
            if a["locking"] != b["locking"]:
                return t, "lock_state", s5, s6
            # 3. distance divergence
            if a["dist"] is not None and b["dist"] is not None:
                if abs(a["dist"] - b["dist"]) > 5000.0:
                    return t, "distance", s5, s6
    return None, "none", None, None


def trace_row(s, n_usv):
    lines = []
    lines.append(f"t={s['t']:.0f}  alive={s['alive']}/{n_usv}  enemy_visible={s['n_enemy']}")
    for name, v in s["usvs"].items():
        d = v["dist"]
        dstr = f"{d/1000:.0f}km" if d is not None else "NA"
        lines.append(f"    {name}: dist_to_enemy={dstr} "
                     f"locking={v['locking']} target={v['locking_unit']} frozen={v['frozen']}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--w5", required=True)
    ap.add_argument("--w6", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--case", default="case")
    ap.add_argument("--n-usv", type=int, default=5)
    args = ap.parse_args()

    g5 = load_game(args.w5)
    g6 = load_game(args.w6)
    w5 = build_series(g5, args.n_usv)
    w6 = build_series(g6, args.n_usv)
    fd_t, fd_signal, s5, s6 = first_divergence(w5, w6)

    lines = []
    lines.append(f"# W6 Paired Trace — {args.case}\n")
    lines.append(f"- W5 game: `{os.path.basename(args.w5)}` result={g5.get('result')} "
                 f"steps={len(w5)} last_sim={w5[-1]['t']:.0f}")
    lines.append(f"- W6 game: `{os.path.basename(args.w6)}` result={g6.get('result')} "
                 f"steps={len(w6)} last_sim={w6[-1]['t']:.0f}")
    lines.append(f"- **FIRST CAUSAL DIVERGENCE**: t={fd_t if fd_t is not None else 'none'}s "
                 f"signal={fd_signal}\n")

    if fd_t is not None:
        # window around divergence: show W5 and W6 side by side
        lines.append("## Divergence window (W5 | W6)\n")
        lo, hi = max(0.0, fd_t - 100.0), fd_t + 100.0
        for s6 in w6:
            if s6["t"] < lo:
                continue
            if s6["t"] > hi:
                break
            s5 = nearest_series(w5, s6["t"])
            lines.append(f"**t={s6['t']:.0f}s**")
            lines.append("W5:")
            lines.append("    " + trace_row(s5, args.n_usv))
            lines.append("W6:")
            lines.append("    " + trace_row(s6, args.n_usv))
            lines.append("")

    lines.append("## End-of-game snapshots\n")
    lines.append("W5 last:\n" + trace_row(w5[-1], args.n_usv))
    lines.append("W6 last:\n" + trace_row(w6[-1], args.n_usv))
    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"trace written: {args.out}")
    print(f"first divergence: t={fd_t}s signal={fd_signal}")


if __name__ == "__main__":
    sys.exit(main())
