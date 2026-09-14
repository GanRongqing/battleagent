#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""dev4_2/offline42.py — 2035-state eligibility funnel + fired count for dev4.2 rule."""
import os
import sys

os.environ.setdefault("W6_ANTI_EVASION", "1")
os.environ.setdefault("W6_MODE", "dev4_2")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "w6_anti_evasion", "dev3", "replay_audit"))
OUT = os.path.dirname(os.path.abspath(__file__))

from replay_analysis import load_states, build_inputs   # noqa: E402
from anti_evasion import config as cfg                   # noqa: E402
from anti_evasion.w6_harness import W6DecisionCore       # noqa: E402
from anti_evasion.metrics import W6Metrics               # noqa: E402


def main():
    states = load_states(os.path.join(ROOT, "w6_anti_evasion", "dev3", "replay_audit",
                                      "allocator_states.jsonl"))
    n = len(states)
    funnel = {"imminent": 0, "high": 0, "free": 0, "deficit": 0, "deadline_ok": 0,
              "coverage_safe": 0, "conc_ok": 0, "fired": 0}
    fired_events = []
    for s in states:
        um = {k: (v if v else None) for k, v in s["usv_map"].items()}
        base = {t: list(u) for t, u in s["base_alloc"].items()}
        alive = {u["name"] for u in s["friendly_usvs"] if u.get("alive")}
        committed = {u for vv in base.values() for u in vv}
        free = [u for u in alive if u not in committed]
        lock = {u["name"]: (u.get("is_locking") and u.get("locking_unit")) for u in s["friendly_usvs"]}
        frozen = {u["name"]: u.get("is_frozen") for u in s["friendly_usvs"]}
        tracks, usvs, _, now, intent, usvp, _ = build_inputs(s)
        core = W6DecisionCore(); core.metrics = W6Metrics()
        f = core.features(tracks, usvs, now, usvp, {})
        risks, corr = f["risks"], f["corridors"]
        def b_eta(C):
            r = risks.get(C)
            b = getattr(r, "breakthrough_eta", None) if r else None
            return b if b is not None and b != float("inf") and b > 0 else None
        def in_time(nm, C):
            if nm not in usvp or C not in corr:
                return False
            pn = core.planner.plan(nm, usvp[nm], corr[C])
            b = b_eta(C)
            return pn is not None and b is not None and \
                pn.intercept_eta * (1 + cfg.SCREEN_ETA_SAFETY) <= b
        high = {C for C in risks
                if b_eta(C) is not None and
                (getattr(risks[C], "risk_score", 0.0) >= cfg.BRK_RISK_HIGH or
                 (getattr(risks[C], "interceptor_deficit", 0) is not None and
                  getattr(risks[C], "interceptor_deficit", 0) < 0))}
        if high:
            funnel["imminent"] += 1
        if any(getattr(risks.get(C), "risk_score", 0.0) >= cfg.BRK_RISK_HIGH for C in high):
            funnel["high"] += 1
        if free:
            funnel["free"] += 1
        need = {}
        for C in high:
            r = risks.get(C)
            risk = getattr(r, "risk_score", 0.0)
            if risk < cfg.BRK_RISK_HIGH:
                continue
            cnt = sum(1 for nm in base.get(C, []) if (nm in lock or nm in frozen) or in_time(nm, C))
            req = cfg.REQUIRED_IN_TIME_CRITICAL if risk >= cfg.CRITICAL_RISK else cfg.REQUIRED_IN_TIME_HIGH
            if cnt < req and len(base.get(C, [])) < cfg.EMERGENCY_CONCENTRATION:
                need[C] = risk
        if need:
            funnel["deficit"] += 1
        fired_now = False
        for u in free:
            if u not in usvp or u in lock or u in frozen:
                continue
            for C in sorted(need, key=lambda x: -need[x]):
                if u in (base.get(C) or []):
                    continue
                if in_time(u, C):
                    funnel["deadline_ok"] += 1
                    # coverage safety for other need corridors
                    unsafe = False
                    for C2 in need:
                        if C2 == C:
                            continue
                        others = [x for x in free if x != u] + \
                                 [x for x in base.get(C2, []) if not (x in lock or x in frozen)]
                        if not any(in_time(x, C2) for x in others):
                            unsafe = True
                            break
                    if unsafe:
                        continue
                    funnel["coverage_safe"] += 1
                    if len(base.get(C, [])) < cfg.EMERGENCY_CONCENTRATION:
                        funnel["conc_ok"] += 1
                        if not fired_now:
                            fired_now = True
                            funnel["fired"] += 1
                            fired_events.append((s["episode"], s["decision_index"], C, u,
                                                 round(need[C], 3)))
    print("states:", n)
    for k in ("imminent", "high", "free", "deficit", "deadline_ok", "coverage_safe",
              "conc_ok", "fired"):
        print(f"  {k}: {funnel[k]}")
    print("fired events sample:", fired_events[:6])
    import csv
    with open(os.path.join(OUT, "DEV4_2_ELIGIBILITY_FUNNEL.csv"), "w", newline="") as fo:
        w = csv.writer(fo)
        w.writerow(["stage", "states_or_targets"])
        for k in ("imminent", "high", "free", "deficit", "deadline_ok", "coverage_safe",
                  "conc_ok", "fired"):
            w.writerow([k, funnel[k]])
    with open(os.path.join(OUT, "W6_DEV4_2_OFFLINE_SUMMARY.csv"), "w", newline="") as fo:
        w = csv.writer(fo)
        w.writerow(["metric", "value"])
        w.writerow(["states", n]); w.writerow(["fired_states", funnel["fired"]])
        w.writerow(["fired_rate", round(funnel["fired"] / n, 4)])
        w.writerow(["dev4_fired_rate", 0.0305]); w.writerow(["dev41_fired_rate", 0.0])


if __name__ == "__main__":
    sys.exit(main())
