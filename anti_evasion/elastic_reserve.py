# -*- coding: utf-8 -*-
"""anti_evasion/elastic_reserve.py — W6-dev4 ElasticReserveManager.

Threat-driven, resource-relative, scale-agnostic reserve CAPACITY estimation. It only
affects allocator availability (which FREE platforms may be pulled), never navigation.

  desired = 0                      when no uncovered high-risk corridor
  desired = f(n_imminent, n_alive) when high-risk / uncovered corridors exist
  endgame (<=1 effective threat)  -> 0 (concentration allowed)

Manager output: reserve set (platforms held back), released list, desired_capacity.
"""
from . import config as cfg


def desired_reserve_capacity(n_alive, n_imminent, n_uncovered_feasible=0):
    """n_imminent: high-risk/critical corridors; n_uncovered_feasible: those with no
    feasible interceptor. Returns integer capacity (resource-relative, no fixed counts)."""
    if n_imminent <= cfg.RESERVE_ENDGAME_MAX_RISK or n_alive <= 0:
        return 0
    if n_uncovered_feasible >= 1 or n_imminent >= cfg.RESERVE_HIGH_RISK_COUNT:
        return int(round(n_alive * cfg.RESERVE_HIGH_RATIO))
    return int(round(n_alive * cfg.RESERVE_BASE_RATIO))


class ElasticReserveManager:
    def __init__(self):
        self.desired = 0
        self.reserve = set()
        self.events_create = 0
        self.events_release = 0

    def update(self, free_platforms, n_alive, n_imminent, n_uncovered_feasible):
        cap = desired_reserve_capacity(n_alive, n_imminent, n_uncovered_feasible)
        free = sorted(free_platforms)
        # create reserve from free if free exceeds capacity already held
        keep = free[:cap] if cap < len(free) else free
        # releases: platforms currently reserved that are no longer needed
        released = [p for p in self.reserve if p not in keep]
        added = [p for p in keep if p not in self.reserve]
        if added:
            self.events_create += 1
        if released:
            self.events_release += 1
        self.desired = cap
        self.reserve = set(keep)
        return set(keep), released, added
