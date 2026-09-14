# -*- coding: utf-8 -*-
"""anti_evasion/adaptive_screen.py — AdaptiveScreenPlanner.

W6 Module 4: dynamic defensive screen — keep resource-relative breakthrough
interception capacity (threat-driven, NOT a fixed "always keep 2 ships" rule).

screen_demand is driven by uncovered breakthrough corridors:
  uncovered_corridors * coverage_per_interceptor_needed
relative to alive USVs (fraction), clamped to [SCREEN_MIN_FRACTION, SCREEN_MAX_FRACTION].
"""
from . import config as cfg


class ScreenPlan:
    __slots__ = ("screen_demand", "screen_positions", "min_capacity",
                 "uncovered_corridors", "reason", "signature")

    def __init__(self, screen_demand, screen_positions, min_capacity,
                 uncovered_corridors, reason, signature=""):
        self.screen_demand = screen_demand
        self.screen_positions = screen_positions
        self.min_capacity = min_capacity
        self.uncovered_corridors = uncovered_corridors
        self.reason = reason
        self.signature = signature

    def to_dict(self):
        return {"screen_demand": self.screen_demand,
                "screen_positions": [list(p) for p in self.screen_positions],
                "min_capacity": self.min_capacity,
                "uncovered_corridors": self.uncovered_corridors,
                "reason": self.reason,
                "signature": self.signature}


class AdaptiveScreenPlanner:
    """Corridor-demand-driven defensive screen.

    demand = max(min_frac, uncovered_corridors_with_risk / alive) but capped by the actual
    uncovered-corridor count (offense starvation guard) and by max_frac.
    A plan signature changes only when the uncovered threat set changes, so we do NOT
    re-reserve every tick (metrics: unique reconfigurations << raw evaluations).
    """

    def __init__(self, min_frac=cfg.SCREEN_MIN_FRACTION, max_frac=cfg.SCREEN_MAX_FRACTION,
                 screen_x=120_000.0):
        self.min_frac = min_frac
        self.max_frac = max_frac
        self.screen_x = screen_x

    def plan(self, alive_usvs, cover_positions, uncovered_corridors, committed_names,
             screen_eta_ok=True):
        n = max(1, alive_usvs)
        # only UNCOVERED + meaningful-risk corridors drive demand
        uncovered = [c for c in uncovered_corridors if c is not None]
        if not uncovered and screen_eta_ok:
            return ScreenPlan(0.0, [], 0, 0, "no_uncovered", "u0")
        # offense starvation guard: never reserve more than the actual uncovered demand
        cap = len(uncovered)
        if not screen_eta_ok:
            cap = max(cap, 1)   # immediate breakthrough threat may force one interceptor
        demand = min(self.max_frac, max(self.min_frac, cap / n))
        capacity = max(1, min(cap, int(round(demand * n))))
        candidates = [p for p in cover_positions if p not in committed_names]
        screen_positions = []
        if candidates:
            span = min(len(candidates), capacity)
            ys = sorted(c[1] for c in candidates)
            y0, y1 = ys[0], ys[-1]
            for i in range(span):
                y = y0 + (y1 - y0) * (i / max(1, span - 1)) if span > 1 else y0
                screen_positions.append((self.screen_x, y))
        reason = (f"uncovered={len(uncovered)}" if uncovered else "no_uncovered")
        sig = f"u{len(uncovered)}_brk{0 if screen_eta_ok else 1}"
        return ScreenPlan(demand, screen_positions, capacity, len(uncovered), reason, sig)
