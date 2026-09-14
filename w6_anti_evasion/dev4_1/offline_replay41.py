#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""dev4_1/offline_replay41.py — offline dev4 vs dev4.1 FREE->imminent counterfactual on the
2035 saved states. dev4.1 rule: FREE u, imminent C (risk>=HIGH), conc(C)<emg, eta<=1.5*ref."""
import os
import random
import sys

os.environ.setdefault("W6_ANTI_EVASION", "1")
os.environ.setdefault("W6_MODE", "dev4_1")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
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
    st_imminent = st_free = st_ratio = st_cap_block = 0
    fired = 0
    fired_events = []
    for s in states:
        um = {k: (v if v else None) for k, v in s["usv_map"].items()}
        base = {t: list(u) for t, u in s["base_alloc"].items()}
        alive = {u["name"] for u in s["friendly_usvs"] if u.get("alive")}
        committed = {u for vv in base.values() for u in vv}
        free = [u for u in alive if u not in committed and not um.get(u)]
        tracks, usvs, _, now, intent, usvp, _ = build_inputs(s)
        core = W6DecisionCore(); core.metrics = W6Metrics()
        f = core.features(tracks, usvs, now, usvp, {})
        risks, corr = f["risks"], f["corridors"]
        imminent = []
        for name, r in risks.items():
            b = getattr(r, "breakthrough_eta", None)
            if b is None or b == float("inf") or b <= 0:
                continue
            if r.risk_score >= cfg.BRK_RISK_HIGH or \
                    (r.interceptor_deficit is not None and r.interceptor_deficit < 0):
                imminent.append(name)
        if imminent:
            st_imminent += 1
        if free:
            st_free += 1
        hit = False
        for C in imminent:
            if C not in corr:
                continue
            conc = len(base.get(C, []))
            if conc >= cfg.EMERGENCY_CONCENTRATION:
                st_cap_block += 1
                continue
            owners = [nm for nm in (base.get(C) or []) if nm in usvp]
            ref = None
            for nm in owners:
                pn = core.planner.plan(nm, usvp[nm], corr[C])
                if pn is not None and (ref is None or pn.intercept_eta < ref):
                    ref = pn.intercept_eta
            for u in free:
                if u not in usvp:
                    continue
                pn = core.planner.plan(u, usvp[u], corr[C])
                if pn is None:
                    continue
                if ref is None or ref <= 0:
                    continue
                ratio = pn.intercept_eta / ref
                if ratio <= cfg.FREE_TO_IMMINENT_ETA_RATIO:
                    st_ratio += 1
                    if not hit:
                        fired += 1
                        hit = True
                        fired_events.append((s["episode"], s["decision_index"], C, u,
                                             round(ratio, 3), conc))
                    break
    print("states:", n)
    print("states with imminent corridor:", st_imminent)
    print("states with FREE platform:", st_free)
    print("states ETA<=1.5x & below cap (fired states):", fired, f"({fired/n:.4f})")
    print("cap-block state-targets:", st_cap_block)
    print("sample events:", fired_events[:5])
    # dev4 baseline ~ A_ORIGINAL 62/2035 = 0.0305 (dev3/4 original), for delta
    print("dev4 (original) fired ~62/2035 = 0.0305")
    with open(os.path.join(OUT, "W6_DEV4_1_OFFLINE_REPLAY.csv"), "w") as fo:
        fo.write("metric,value\n")
        for k, v in [("states", n), ("imminent_states", st_imminent),
                     ("free_states", st_free), ("ratio_eligible_or_fired", fired),
                     ("fired_rate", round(fired / n, 4)),
                     ("cap_block_targets", st_cap_block),
                     ("dev4_fired_rate", 0.0305)]:
            fo.write(f"{k},{v}\n")


if __name__ == "__main__":
    sys.exit(main())
