# -*- coding: utf-8 -*-
"""anti_evasion/commitment.py — W6-dev4 CommitmentClassifier (four-state model).

FREE / SOFT_COMMITTED / HARD_COMMITTED / RESERVE are pure, auditable classifications of the
LEGAL platform state (alive / has-target / locking / frozen). They never touch navigation.

  HARD_COMMITTED (never allocator-releasable):
     - active lock (is_locking + locking_unit)
     - target frozen (is_frozen: hit-freeze / second-hit follow-up window)
     - dead
  SOFT_COMMITTED: alive, has a target, but not locking and not frozen
  FREE:           alive, no target
  RESERVE:        a FREE platform the ElasticReserveManager holds back (classifier is unaware)
"""
FREE = "FREE"
SOFT = "SOFT_COMMITTED"
HARD = "HARD_COMMITTED"
RESERVE = "RESERVE"


def classify_platform(usv, has_target, is_locking=None, is_frozen=None, alive=None):
    """Classify a single platform from legal fields only."""
    if alive is None:
        alive = usv.get("is_alive", True)
    if not alive:
        return HARD
    if is_locking is None:
        is_locking = bool(usv.get("is_locking")) and bool(usv.get("locking_unit"))
    if is_frozen is None:
        is_frozen = bool(usv.get("is_frozen"))
    if is_locking or is_frozen:
        return HARD
    if has_target:
        return SOFT
    return FREE


def classify_all(obs_usvs, target_map, reserve_set=None):
    """obs_usvs: platform dicts; target_map: {platform: target|None};
    reserve_set: platforms the reserve manager holds (treated RESERVE).
    Returns {platform: class}."""
    reserve_set = reserve_set or set()
    out = {}
    for u in obs_usvs:
        name = u.get("name")
        cls = classify_platform(u, bool(target_map.get(name)),
                                is_locking=bool(u.get("is_locking")) and bool(u.get("locking_unit")),
                                is_frozen=bool(u.get("is_frozen")),
                                alive=bool(u.get("is_alive")))
        if cls == FREE and name in reserve_set:
            cls = RESERVE
        out[name] = cls
    return out
