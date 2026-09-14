# -*- coding: utf-8 -*-
"""anti_evasion/releasable_pool.py — W6-dev4 ReleasablePoolBuilder.

Builds the allocator candidate pool:
    FREE + eligible SOFT_COMMITTED + released RESERVE
with HARD_COMMITTED never included.

Eligibility of a SOFT platform is conservative and auditable:
  - it has a target (SOFT),
  - releasing it does not strand its current target (>= 2 assigned, or its target is not an
    imminent high-risk corridor),
  - hysteresis: re-using an existing HandoffEvaluator-style benefit (the candidate only
    enters the pool; the actual switch still requires a >= HANDOFF_MIN_BENEFIT ETA gain on
    the destination target vs the current lead there).
"""
from . import config as cfg
from .commitment import FREE, SOFT, HARD, RESERVE


def build_releasable_pool(cls_map, assigned_map, base_alloc, risks, now, min_benefit=None):
    """assigned_map: {platform: target|None} (current commitments).
    base_alloc: {target: [platforms]} (all current assignments incl. prior steps).
    returns (pool, reasons) with pool = list of platforms usable as reallocation candidates
    (FREE + eligible SOFT); reasons {platform: (reason, from_target)}.
    """
    min_benefit = cfg.HANDOFF_MIN_BENEFIT if min_benefit is None else min_benefit
    free = [p for p, c in cls_map.items() if c == FREE]
    reasons = {}
    soft_ok = []
    for p, c in cls_map.items():
        if c != SOFT:
            continue
        tgt = assigned_map.get(p)
        if not tgt:
            continue
        assigned = base_alloc.get(tgt) or []
        covered = len(assigned) >= 2
        imminent = False
        r = (risks or {}).get(tgt)
        if r is not None:
            b = getattr(r, "breakthrough_eta", None)
            if b not in (None, float("inf")) and b > 0:
                too_late = r.interceptor_deficit is not None and r.interceptor_deficit < 0
                imminent = (r.risk_score >= cfg.BRK_RISK_HIGH) or too_late
        if covered or not imminent:
            soft_ok.append(p)
            reasons[p] = ("SOFT_RELEASABLE", tgt)
    return free + soft_ok, reasons
