#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""dev4/quality_audit/near_miss_audit.py — near-miss eligibility gate attribution (offline).

For sampled saved states, find SOFT/free candidates with a potentially beneficial alternative
(per the offline counterfactual: dest imminent/uncovered, or candidate ETA < current lead by
>= HANDOFF_MIN_BENEFIT) and classify why dev4 would NOT reallocate: gate reason.
"""
import csv
import json
import os
import random
import sys

os.environ.setdefault("W6_ANTI_EVASION", "1")
os.environ.setdefault("W6_MODE", "dev4")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "w6_anti_evasion", "dev3", "replay_audit"))
OUT = os.path.dirname(os.path.abspath(__file__))

from replay_analysis import load_states, build_inputs   # noqa: E402
from anti_evasion import config as cfg                   # noqa: E402
from anti_evasion.w6_harness import W6DecisionCore       # noqa: E402
from anti_evasion.metrics import W6Metrics               # noqa: E402

MINB = cfg.HANDOFF_MIN_BENEFIT


def main():
    states = load_states(os.path.join(ROOT, "w6_anti_evasion", "dev3", "replay_audit",
                                      "allocator_states.jsonl"))
    rng = random.Random(1)
    sample = rng.sample(states, min(400, len(states)))
    reasons = {"NOT_SOFT": 0, "COVERAGE_BLOCK": 0, "HYSTERESIS": 0,
               "RESERVE_BLOCK": 0, "NO_RELEASE_SLOT": 0, "OTHER": 0,
               "WOULD_REALLOC": 0, "NO_BENEFIT": 0}
    near = []
    for s in sample:
        usvmap = {k: (v if v else None) for k, v in s["usv_map"].items()}
        lock = {u["name"]: (u.get("is_locking") and u.get("locking_unit"))
                for u in s["friendly_usvs"]}
        frozen = {u["name"]: u.get("is_frozen") for u in s["friendly_usvs"]}
        alive = {u["name"] for u in s["friendly_usvs"] if u.get("alive")}
        base = {t: list(u) for t, u in s["base_alloc"].items()}
        cov = {}
        for t, us in base.items():
            cov.setdefault(t, 0)
            cov[t] += len(us)
        for t in usvmap.values():
            if t:
                cov.setdefault(t, 0)
        tracks, usvs, _, now, intent, usvp, usvs_ = build_inputs(s)
        core = W6DecisionCore(); core.metrics = W6Metrics()
        feat = core.features(tracks, usvs, now, usvp, usvs_)
        risks, corr, plans = feat["risks"], feat["corridors"], feat["intercept_plans"]
        imminent = set()
        for name, r in risks.items():
            b = getattr(r, "breakthrough_eta", None)
            if b is None or b == float("inf") or b <= 0:
                continue
            if r.interceptor_deficit is not None and r.interceptor_deficit < 0:
                imminent.add(name)
            if (r.risk_score >= cfg.BRK_RISK_HIGH):
                imminent.add(name)
        targets = [t for t in corr.keys()]
        committed = {u for vv in base.values() for u in vv}
        for p in sorted(alive):
            if p not in usvp:
                continue
            cur = usvmap.get(p)
            best_t, best_e = None, None
            for tgt in targets:
                pn = core.planner.plan(p, usvp[p], corr[tgt])
                if pn is None:
                    continue
                if best_e is None or pn.intercept_eta < best_e:
                    best_t, best_e = tgt, pn.intercept_eta
            if best_t is None or best_t == cur:
                continue
            lead_e = None
            for name, uu in (usvmap or {}).items():
                if uu == best_t:
                    pn = core.planner.plan(name, usvp.get(name), corr.get(best_t))
                    if pn is not None:
                        lead_e = pn.intercept_eta
            cur_e = None
            if cur and cur in corr:
                pn = core.planner.plan(p, usvp[p], corr[cur])
                cur_e = pn.intercept_eta if pn else None
            imminent_alt = best_t in imminent
            beat_lead = lead_e is not None and best_e < lead_e * (1 - MINB)
            beat_self = cur_e is not None and best_e < cur_e * (1 - MINB)
            beneficial = imminent_alt or beat_lead or beat_self
            if not beneficial:
                reasons["NO_BENEFIT"] += 1
                continue
            # gate attribution
            if p in lock or p in frozen:
                gate = "NOT_SOFT"
            elif cur and base.get(cur) and len(base.get(cur, [])) <= 1:
                gate = "COVERAGE_BLOCK"
            elif cur is None and p in committed:
                gate = "RESERVE_BLOCK"
            elif (not imminent_alt) and (not beat_self) and (not beat_lead):
                gate = "HYSTERESIS"
            elif not (imminent_alt or beat_lead or beat_self):
                gate = "INSUFFICIENT_BENEFIT"
            else:
                gate = "WOULD_REALLOC"
            reasons[gate] = reasons.get(gate, 0) + 1
            near.append({"state": s["episode"] + "_" + str(s["decision_index"]),
                         "seed": s["seed"], "sim_time": s["sim_time"],
                         "platform": p, "current": cur, "alternative": best_t,
                         "cur_eta": round(cur_e, 1) if cur_e else None,
                         "alt_eta": round(best_e, 1),
                         "lead_eta": round(lead_e, 1) if lead_e else None,
                         "alt_imminent": imminent_alt, "block": gate})
    with open(os.path.join(OUT, "NEAR_MISS_GATE_SUMMARY.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["gate_reason", "count"])
        for k in sorted(reasons):
            w.writerow([k, reasons[k]])
    # representative near-miss (up to 10)
    keep = [n for n in near if n["block"] != "WOULD_REALLOC"][:10]
    with open(os.path.join(OUT, "NEAR_MISS_EVENTS.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(near[0].keys()) if near else ["state"])
        w.writeheader()
        for n in keep:
            w.writerow(n)
    print("sampled states:", len(sample))
    print("gate reasons:", reasons)
    print("potentially beneficial candidates:", len(near))
    print("near-miss (blocked) representatives:", len(keep))


def free_of(s, base):
    committed = {u for vv in base.values() for u in vv}
    alive = {u["name"] for u in s["friendly_usvs"] if u.get("alive")}
    return alive - committed


if __name__ == "__main__":
    sys.exit(main())
