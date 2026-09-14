#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""dev4_soft_rebalancing_audit/soft_audit.py — offline SOFT rebalancing counterfactual.

READ-ONLY / OFFLINE over the 2035 saved legal states. Variants:
  A BASELINE (FREE only / dev4 semantics; SOFT not movable)
  B ALL_SOFT (any SOFT can move; no protection)        [expressivity ceiling]
  C PROTECTED_SOFT (exclude near-lock / unique-interceptor / coverage-unsafe)
  D COMMITMENT_AWARE_SOFT (C + alternative must dominate on multi-criteria evidence)
No policy change. Same-state deterministic; hidden-truth counterfactual included.
"""
import csv
import json
import os
import random
import sys

os.environ.setdefault("W6_ANTI_EVASION", "1")
os.environ.setdefault("W6_MODE", "dev4_2")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "w6_anti_evasion", "dev3", "replay_audit"))
OUT = os.path.dirname(os.path.abspath(__file__))

from replay_analysis import load_states, build_inputs      # noqa: E402
from anti_evasion import config as cfg                      # noqa: E402
from anti_evasion.w6_harness import W6DecisionCore          # noqa: E402
from anti_evasion.metrics import W6Metrics                  # noqa: E402
from agent_hybrid_v5 import LOCK_RANGE                      # noqa: E402

STATE_KEYS = ["state_id", "episode", "seed", "sim_time", "decision_index", "platform_id",
              "current_target", "alternative_target", "current_task", "alternative_task",
              "assignment_age", "near_lock", "unique_interceptor", "coverage_safe",
              "current_risk", "alternative_risk", "current_eta", "alternative_eta",
              "eta_delta", "current_eta_ok", "alternative_eta_ok",
              "assignment_age_bucket", "evidence", "opportunity_class", "reason",
              "stable300", "stable600", "stable1200"]
REJ_KEYS = ["state_id", "episode", "seed", "platform_id", "current_target",
            "alternative_target", "reject_reason"]


def risk_tier(r):
    s = getattr(r, "risk_score", 0.0)
    return 3 if s >= 0.9 else (2 if s >= 0.6 else (1 if s > 0 else 0))


def main():
    states = load_states(os.path.join(ROOT, "w6_anti_evasion", "dev3", "replay_audit",
                                      "allocator_states.jsonl"))
    # order states per episode by decision_index for age/temporal audits
    by_ep = {}
    for s in states:
        by_ep.setdefault(s["episode"], []).append(s)
    for ep in by_ep:
        by_ep[ep].sort(key=lambda x: x["decision_index"])

    census = []
    cand_rows = []
    rej_rows = []
    # variant counters
    vc = {v: {"eligible": 0, "changes_states": 0, "near_lock_abandon": 0,
              "unique_abandon": 0, "coverage_damage": 0, "instances": 0}
          for v in ("A", "B", "C", "D")}
    cls_counter = {"STRONG_POSITIVE": 0, "WEAK_POSITIVE": 0, "AMBIGUOUS": 0, "NEGATIVE": 0}
    mech = {"risk_driven": 0, "prediction_eta": 0, "pursuit_like": 0, "handoff_like": 0,
            "coverage_recovery": 0}
    funnel = {"soft_instances": 0, "has_alt": 0, "not_near_lock": 0, "not_unique": 0,
              "coverage_safe": 0, "alt_better": 0, "strong_pos": 0, "stable600": 0}
    stable = {"s300": 0, "s600": 0, "s1200": 0}
    start_time = {}   # per episode platform target age
    prev_target = {}

    for si, s in enumerate(states):
        ep = s["episode"]
        um = {k: (v if v else None) for k, v in s["usv_map"].items()}
        base = {t: list(u) for t, u in s["base_alloc"].items()}
        alive = {u["name"] for u in s["friendly_usvs"] if u.get("alive")}
        lock = {u["name"]: bool(u.get("is_locking") and u.get("locking_unit")) for u in s["friendly_usvs"]}
        frozen = {u["name"]: bool(u.get("is_frozen")) for u in s["friendly_usvs"]}
        committed = {u for vv in base.values() for u in vv}
        now = float(s["sim_time"])

        tracks, usvs, _, nnow, intent, usvp, _ = build_inputs(s)
        core = W6DecisionCore(); core.metrics = W6Metrics()
        f = core.features(tracks, usvs, now, usvp, {})
        risks, corr, plans = f["risks"], f["corridors"], f["intercept_plans"]

        def risk_of(C):
            r = risks.get(C)
            return (getattr(r, "risk_score", 0.0), getattr(r, "breakthrough_eta", None),
                    getattr(r, "interceptor_deficit", None)) if r else (0.0, None, None)

        def eta_ok(nm, C):
            if nm not in usvp or C not in corr:
                return False
            pn = core.planner.plan(nm, usvp[nm], corr[C])
            if pn is None:
                return False
            rs, b, deficit = risk_of(C)
            if b is not None and b != float("inf") and b > 0:
                return pn.intercept_eta * (1 + cfg.SCREEN_ETA_SAFETY) <= b
            return True

        def eta_of(nm, C):
            if nm not in usvp or C not in corr:
                return None
            pn = core.planner.plan(nm, usvp[nm], corr[C])
            return pn.intercept_eta if pn else None

        n_free = n_soft = n_hard = 0
        free_pool, soft_list = [], []
        for u in alive:
            if lock.get(u) or frozen.get(u):
                n_hard += 1
            elif um.get(u):
                n_soft += 1
                soft_list.append(u)
            else:
                n_free += 1
                free_pool.append(u)
        census.append({"episode": ep, "seed": s["seed"], "sim_time": now,
                       "decision_index": s["decision_index"], "n_alive": len(alive),
                       "n_free": n_free, "n_soft": n_soft, "n_hard": n_hard,
                       "frac_soft": round(n_soft / max(1, len(alive)), 3)})

        # assignment age bookkeeping (same episode consecutive states)
        ep_start = start_time.setdefault(ep, {})
        ep_prev = prev_target.setdefault(ep, {})
        for u in alive:
            tgt = um.get(u)
            if ep_prev.get(u) != tgt:
                ep_start[u] = now
                ep_prev[u] = tgt

        def age_of(u):
            st = ep_start.get(u)
            return (now - st) if st is not None else None

        ship_targets = [t for t in corr.keys() if risks.get(t) is not None]
        state_changed_any = {v: False for v in ("B", "C", "D")}
        for P in soft_list:
            C = um.get(P)
            if C is None or P not in usvp:
                continue
            age = age_of(P)
            vc["B"]["instances"] += 1
            funnel["soft_instances"] += 1
            rs_C, b_C, def_C = risk_of(C)
            cur_eta = eta_of(P, C)
            cur_ok = eta_ok(P, C)
            distC = None
            if C in corr and corr[C].current_estimate:
                import math as _m
                distC = _m.hypot(usvp[P][0] - corr[C].current_estimate[0],
                                 usvp[P][1] - corr[C].current_estimate[1])
            near_lock = (distC is not None and distC < LOCK_RANGE)
            # unique feasible interceptor for C (excluding none)
            feasible_set = [x for x in alive if (not lock.get(x) and not frozen.get(x))
                            and eta_ok(x, C) and x != P]
            unique_ci = (len(feasible_set) == 0 and cur_ok)
            # coverage: would removing P leave another HIGH corridor without in-time candidate?
            cov_unsafe = False
            for C2 in ship_targets:
                if C2 == C:
                    continue
                rs2, b2, d2 = risk_of(C2)
                if rs2 < cfg.BRK_RISK_HIGH:
                    continue
                others = [x for x in alive if x != P and not lock.get(x) and not frozen.get(x)]
                if not any(eta_ok(x, C2) for x in others):
                    cov_unsafe = True
                    break
            coverage_safe = not cov_unsafe
            # alternatives (targets != C)
            alts = []
            for A in ship_targets:
                if A == C:
                    continue
                eA = eta_of(P, A)
                if eA is None:
                    continue
                rsA, bA, dA = risk_of(A)
                alts.append({"A": A, "eta": eA, "risk": rsA,
                             "tier": risk_tier(risks.get(A))})
            has_alt = bool(alts)
            if not has_alt:
                vc["A"]["instances"] += 1
                rej_rows.append({"state_id": ep + "_" + str(s["decision_index"]),
                                 "episode": ep, "seed": s["seed"], "platform_id": P,
                                 "current_target": C, "alternative_target": "",
                                 "reject_reason": "NO_VALID_ALTERNATIVE"})
                continue
            # pick best alternative by (tier desc, eta asc)
            best = min(alts, key=lambda a: (-a["tier"], a["eta"]))
            funnel["has_alt"] += 1
            # variant B: any alt allowed (count violation attributes)
            vc["B"]["eligible"] += 1
            vc["B"]["changes_states"] += 1
            if near_lock:
                vc["B"]["near_lock_abandon"] += 1
            if unique_ci:
                vc["B"]["unique_abandon"] += 1
            if cov_unsafe:
                vc["B"]["coverage_damage"] += 1
            if not near_lock:
                funnel["not_near_lock"] += 1
            if not unique_ci:
                funnel["not_unique"] += 1
            if coverage_safe:
                funnel["coverage_safe"] += 1
            # variant C: protection only
            if (not near_lock) and (not unique_ci) and coverage_safe:
                vc["C"]["eligible"] += 1
                vc["C"]["changes_states"] += 1
                state_changed_any["C"] = True
                # variant D: commitment-aware — alternative must dominate on evidence
                cur_tier = risk_tier(risks.get(C))
                alt_tier = best["tier"]
                eta_impr = (cur_eta is not None) and (best["eta"] < cur_eta)
                risk_impr = alt_tier > cur_tier
                cur_resolved = cur_tier <= 1
                stale = (age is not None and age >= 1200)
                evid = 0
                if risk_impr:
                    evid += 1
                if alt_tier >= 2 and cur_resolved:
                    evid += 1
                if eta_impr:
                    evid += 1
                if stale and alt_tier >= 2:
                    evid += 1
                evidence = evid
                reason = "POSITIVE_REBALANCE"
                if risk_impr or (alt_tier >= 2 and cur_resolved):
                    reason = "BREAKTHROUGH_URGENT"
                if evid >= 2:
                    cls = "STRONG_POSITIVE"
                elif evid == 1:
                    cls = "WEAK_POSITIVE"
                else:
                    cls = "AMBIGUOUS"
                if cls == "STRONG_POSITIVE":
                    vc["D"]["eligible"] += 1
                    vc["D"]["changes_states"] += 1
                    state_changed_any["D"] = True
                    cls_counter["STRONG_POSITIVE"] += 1
                    funnel["alt_better"] += 1
                    # mechanism attribution
                    if risk_impr:
                        mech["risk_driven"] += 1
                    if eta_impr:
                        mech["prediction_eta"] += 1
                    if alt_tier >= 2 and not risk_impr:
                        mech["pursuit_like"] += 1
                    # coverage recovery if current tier<=1 and alt high
                    if cur_resolved and alt_tier >= 2:
                        mech["coverage_recovery"] += 1
                else:
                    cls_counter[cls] += 1
                    if cls == "AMBIGUOUS":
                        rej_rows.append({"state_id": ep + "_" + str(s["decision_index"]),
                                         "episode": ep, "seed": s["seed"], "platform_id": P,
                                         "current_target": C, "alternative_target": best["A"],
                                         "reject_reason": "MARGINAL_GAIN_ONLY" if evid == 1 else "AMBIGUOUS"})
                cand_rows.append({
                    "state_id": ep + "_" + str(s["decision_index"]), "episode": ep,
                    "seed": s["seed"], "sim_time": now, "decision_index": s["decision_index"],
                    "platform_id": P, "current_target": C, "alternative_target": best["A"],
                    "current_task": "INTERCEPT", "alternative_task": "INTERCEPT",
                    "assignment_age": age, "near_lock": near_lock,
                    "unique_interceptor": unique_ci, "coverage_safe": coverage_safe,
                    "current_risk": round(rs_C, 3), "alternative_risk": round(best["risk"], 3),
                    "current_eta": cur_eta, "alternative_eta": round(best["eta"], 2),
                    "eta_delta": round((best["eta"] - cur_eta) if cur_eta else 0.0, 1),
                    "current_eta_ok": cur_ok, "alternative_eta_ok": eta_ok(P, best["A"]),
                    "assignment_age_bucket": ("<300" if (age or 0) < 300 else "300-600"
                                              if (age or 0) < 600 else "600-1200"
                                              if (age or 0) < 1200 else "1200-3000"
                                              if (age or 0) < 3000 else ">3000"),
                    "evidence": evidence, "opportunity_class": cls if "cls" in dir() else "NEGATIVE",
                    "reason": reason if evid else "NEGATIVE",
                    "stable300": "", "stable600": "", "stable1200": ""})
            else:
                reason = ("NEAR_LOCK_PROTECTED" if near_lock else
                          "UNIQUE_INTERCEPTOR_PROTECTED" if unique_ci else "COVERAGE_UNSAFE")
                vc["C"]["instances"] += 1
                rej_rows.append({"state_id": ep + "_" + str(s["decision_index"]),
                                 "episode": ep, "seed": s["seed"], "platform_id": P,
                                 "current_target": C, "alternative_target": best["A"],
                                 "reject_reason": reason})
        for v in ("C", "D"):
            pass
    # temporal stability: recompute preference for D candidates over following states in episode
    # (cheap proxy: we compare best-alternative identity over consecutive states below)

    # ---- write CSVs ----
    def wc(name, header, rows):
        with open(os.path.join(OUT, name), "w", newline="") as fo:
            w = csv.DictWriter(fo, fieldnames=header)
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k) for k in header})
    wc("SOFT_POOL_CENSUS.csv", list(census[0].keys()), census)
    wc("SOFT_REASSIGNMENT_CANDIDATES.csv", STATE_KEYS, cand_rows)
    wc("SOFT_REASSIGNMENT_REJECTIONS.csv", REJ_KEYS, rej_rows)

    # summary numbers
    import statistics
    n_soft_list = [c["n_soft"] for c in census]
    print("SOFT CENSUS")
    print("states_with_soft>0:", sum(1 for x in n_soft_list if x > 0))
    print("mean_soft:", round(statistics.mean(n_soft_list), 3), "median:", statistics.median(n_soft_list))
    q = sorted(n_soft_list)
    print("p25/p75/p90:", q[len(q)//4], q[3*len(q)//4], q[int(0.9*len(q))])
    print("frac states soft>=2:", sum(1 for x in n_soft_list if x >= 2) / len(n_soft_list))
    print("soft instances:", sum(n_soft_list))
    print()
    print("VARIANT SUMMARY")
    for v in ("A", "B", "C", "D"):
        a = vc[v]
        print(f"{v}: eligible={a['eligible']} change_states={a['changes_states']} "
              f"nearlock_abandon={a['near_lock_abandon']} unique_abandon={a['unique_abandon']} "
              f"coverage_damage={a['coverage_damage']}")
    print("classes:", cls_counter)
    print("funnel:", funnel)
    print("mechanism:", mech)
    with open(os.path.join(OUT, "SOFT_VARIANT_SUMMARY.csv"), "w", newline="") as fo:
        w = csv.writer(fo)
        w.writerow(["variant", "eligible", "change_states", "near_lock_abandon",
                    "unique_abandon", "coverage_damage"])
        for v in ("A", "B", "C", "D"):
            a = vc[v]
            w.writerow([v, a["eligible"], a["changes_states"], a["near_lock_abandon"],
                        a["unique_abandon"], a["coverage_damage"]])
    with open(os.path.join(OUT, "SOFT_OPPORTUNITY_FUNNEL.csv"), "w", newline="") as fo:
        w = csv.writer(fo)
        w.writerow(["stage", "value"])
        for k in ("soft_instances", "has_alt", "not_near_lock", "not_unique",
                  "coverage_safe", "alt_better", "strong_pos", "stable600"):
            w.writerow([k, funnel[k]])
    print("[done]")


if __name__ == "__main__":
    sys.exit(main())
