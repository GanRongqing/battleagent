#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""dev4/offline/expressivity_counterfactual.py — offline decision-expressivity test on the
2035 saved allocator states.

Scenarios (purely diagnostic; nothing is run live):
  A ORIGINAL      : candidates = FREE pool only (dev3 behaviour)
  B ONE_FREE      : additionally release ONE lowest-cost SOFT platform
  C SOFT_RELEASE  : all SOFT platforms are releasable candidates
  D ELASTIC_POOL  : SOFT + risk-elastic reserve release (reserve shrinks when risk low)

For each state we count the candidate pool and whether the W6 features can produce a
valid, explainable reassignment (soft-movable platform, risk reinforcement into an
uncovered corridor, handoff to a strictly better lead). Deterministic offline.
"""
import csv
import json
import math
import os
import sys

os.environ.setdefault("W6_ANTI_EVASION", "1")
os.environ.setdefault("W6_MODE", "dev3")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "w6_anti_evasion", "dev3", "replay_audit"))
OUT = os.path.dirname(os.path.abspath(__file__))

from replay_analysis import load_states, build_inputs            # noqa: E402
from anti_evasion.w6_harness import W6DecisionCore               # noqa: E402
from anti_evasion.metrics import W6Metrics                       # noqa: E402
from anti_evasion import config as cfg                           # noqa: E402
from agent_hybrid_v5 import ThreatAllocator                      # noqa: E402

MIN_BEN = cfg.HANDOFF_MIN_BENEFIT


def pools(state):
    """Classify each alive USV. Returns dicts free/soft/hard by usv name + target map."""
    usvmap = {k: (v if v else None) for k, v in state["usv_map"].items()}
    lock = {u["name"]: (u.get("is_locking") and u.get("locking_unit")) for u in state["friendly_usvs"]}
    frozen = {u["name"]: u.get("is_frozen") for u in state["friendly_usvs"]}
    alive = {u["name"] for u in state["friendly_usvs"] if u.get("alive")}
    free, soft, hard = {}, {}, {}
    for name in alive:
        tgt = usvmap.get(name)
        if lock.get(name) or frozen.get(name):
            hard[name] = tgt
        elif tgt:
            soft[name] = tgt
        else:
            free[name] = None
    return usvmap, free, soft, hard, lock


def main():
    states = load_states(os.path.join(ROOT, "w6_anti_evasion", "dev3", "replay_audit",
                                      "allocator_states.jsonl"))
    print("states:", len(states))
    scen_cols = ["scenario", "mean_free", "mean_soft", "mean_hard", "mean_reserve_est",
                 "handoff_eligible_states", "handoff_elig_rate",
                 "change_states", "change_rate"]
    rows = []
    for scen in ["A_ORIGINAL", "B_ONE_FREE", "C_SOFT_RELEASE", "D_ELASTIC_POOL"]:
        total_free = total_soft = total_hard = total_res = 0
        elig = 0
        change = 0
        for s in states:
            usvmap, free, soft, hard, lock = pools(s)
            tracks, usvs, usv_map, now, intent, usvp, usvs_ = build_inputs(s)
            # reserve estimate: unavailable-kept platforms approximated by imminence
            base = {t: list(u) for t, u in s["base_alloc"].items()}
            core = W6DecisionCore(); core.metrics = W6Metrics()
            feat = core.features(tracks, usvs, now, usvp, usvs_)
            risks, corr, plans = feat["risks"], feat["corridors"], feat["intercept_plans"]
            imminent = []
            for name, r in risks.items():
                b = getattr(r, "breakthrough_eta", None)
                if b is None or b == float("inf") or b <= 0:
                    continue
                too_late = r.interceptor_deficit is not None and r.interceptor_deficit < 0
                if (r.risk_score >= cfg.BRK_RISK_HIGH) or too_late:
                    imminent.append(name)
            res_est = min(len(free), max(0, len(imminent) - 1)) if imminent else 0
            total_free += len(free); total_soft += len(soft); total_hard += len(hard)
            total_res += res_est
            # candidate pool for the scenario
            cand = list(free)
            if scen in ("B_ONE_FREE",):
                # release one SOFT: the one whose current target has most assigned
                if soft:
                    bycov = {}
                    for nm, tgt in soft.items():
                        bycov.setdefault(tgt, 0)
                        bycov[tgt] += 1
                    # release a soft whose target is most crowded OR (fallback) any
                    pick = max(soft.items(), key=lambda kv: bycov.get(kv[1], 0) + (1 if free else 0))
                    cand.append(pick[0])
            elif scen in ("C_SOFT_RELEASE", "D_ELASTIC_POOL"):
                cand = list(free) + list(soft)
            targets = [t for t in corr.keys() if t in base or
                       any(v == t for v in (usvmap or {}).values())]
            changed_here = 0
            elig_here = 0
            for u in cand:
                if u not in usvp:
                    continue
                best_t, best_e = None, None
                for tgt in targets:
                    p = core.planner.plan(u, usvp[u], corr[tgt])
                    if p is None:
                        continue
                    if best_e is None or p.intercept_eta < best_e:
                        best_t, best_e = tgt, p.intercept_eta
                if best_t is None:
                    continue
                cur_t = usvmap.get(u) if u not in free else None
                if cur_t is None or cur_t != best_t:
                    lead = None
                    for name, uu in (usvmap or {}).items():
                        if name == best_t:
                            lead = uu
                    lead_e = None
                    if lead and lead in usvp:
                        p = core.planner.plan(lead, usvp[lead], corr.get(best_t))
                        if p is not None:
                            lead_e = p.intercept_eta
                    reason = None
                    if best_t in imminent:
                        reason = "BREAKTHROUGH_URGENT"
                    elif cur_t is not None:
                        pcur = core.planner.plan(u, usvp[u], corr.get(cur_t))
                        cur_e = pcur.intercept_eta if pcur else None
                        if cur_e and best_e < cur_e * (1 - MIN_BEN):
                            reason = "BETTER_INTERCEPTOR"
                    if reason and u not in hard:
                        elig_here = 1
                        if best_t in imminent or lead_e is None or \
                                best_e < (lead_e or 1e18) * (1 - MIN_BEN):
                            changed_here = 1
            elig += elig_here
            change += changed_here
        n = len(states)
        rows.append([scen, total_free / n, total_soft / n, total_hard / n, total_res / n,
                     elig, elig / n, change, change / n])
        print(f"{scen}: free={total_free/n:.3f} soft={total_soft/n:.3f} hard={total_hard/n:.3f} "
              f"res~{total_res/n:.3f} handoff_elig={elig}/{n} ({elig/n:.4f}) "
              f"change={change}/{n} ({change/n:.4f})")
    with open(os.path.join(OUT, "decision_expressivity_counterfactual.csv"), "w",
              newline="") as f:
        w = csv.writer(f)
        w.writerow(scen_cols)
        w.writerows(rows)
    print("[done]")


if __name__ == "__main__":
    sys.exit(main())
