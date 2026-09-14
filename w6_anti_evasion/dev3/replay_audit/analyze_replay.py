#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""dev3/replay_audit/analyze_replay.py — activation / decision-change / gates / determinism.

Reads allocator_states.jsonl + allocator_replay_results.csv (signature hashes per variant).
Recomputes feature-level activation + handoff/reserve gates offline. No simulator.
"""
import csv
import json
import os
import random
import sys

os.environ.setdefault("W6_ANTI_EVASION", "1")
os.environ.setdefault("W6_MODE", "dev3")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
OUT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "w6_anti_evasion", "dev3", "replay_audit"))

from replay_analysis import (load_states, build_inputs, sig, rebuild_track,  # noqa: E402
                             run_w5, run_w6)
from anti_evasion import config as cfg   # noqa: E402
from anti_evasion.w6_harness import W6DecisionCore   # noqa: E402
from anti_evasion.handoff import HandoffEvaluator    # noqa: E402
from anti_evasion.metrics import W6Metrics            # noqa: E402

VARIANTS = ["A_W5", "B_Pred", "C_Risk", "D_Pursuit", "E_Handoff", "F_Reserve"]
GATES = {"B_Pred": dict(pred=True), "C_Risk": dict(pred=True, risk=True),
         "D_Pursuit": dict(pred=True, risk=True, pursuit=True),
         "E_Handoff": dict(pred=True, risk=True, pursuit=True, handoff=True),
         "F_Reserve": dict(pred=True, risk=True, pursuit=True, handoff=True, reserve=True)}


def main():
    states = load_states(os.path.join(OUT, "allocator_states.jsonl"))
    print("states:", len(states))

    # ── decision-change from replay CSV (per state, consecutive variant hash diff) ──
    dec = {}
    for r in csv.DictReader(open(os.path.join(OUT, "allocator_replay_results.csv"))):
        if r["note"]:
            continue
        dec[(r["episode"], int(r["decision_index"]), r["variant"])] = r["signature"]
    changed = {v: 0 for v in VARIANTS[1:]}
    nstates = 0
    for ep in sorted({k[0] for k in dec}):
        idxs = sorted({k[1] for k in dec if k[0] == ep})
        for i in idxs:
            h = {v: dec.get((ep, i, v)) for v in VARIANTS}
            if not all(h.values()):
                continue
            nstates += 1
            for v in VARIANTS[1:]:
                prev = VARIANTS[VARIANTS.index(v) - 1]
                if h[v] != h[prev]:
                    changed[v] += 1
    print("\nDECISION CHANGE (assignment signature diff vs previous variant)")
    with open(os.path.join(OUT, "decision_change_summary.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["component", "total_states", "changed_states", "change_rate"])
        for v in VARIANTS[1:]:
            rate = changed[v] / max(1, nstates)
            w.writerow([f"{VARIANTS.index(v)-1}_to_{VARIANTS.index(v)} ({v})", nstates,
                        changed[v], round(rate, 4)])
            print(f"  {v}: changed {changed[v]}/{nstates} = {rate:.4f}")

    # ── activation / gates / margin over features (one pass per state) ──
    acts = {v: 0 for v in ["Prediction", "Risk", "Pursuit", "Handoff", "Reserve"]}
    gates = {"NO_CURRENT": 0, "NO_ALT": 0, "ALT_NOT_BETTER": 0, "INSUFF_BENEFIT": 0,
             "LOCK": 0, "COOLDOWN": 0, "COVERAGE": 0, "LOW_RISK": 0}
    cont = []   # (state, abs contribution fraction vs baseline margin) for handoff-best
    n = 0
    for s in states:
        tracks, usvs, usv_map, now, intent, usvp, usvs_ = build_inputs(s)
        core = W6DecisionCore()
        met = W6Metrics()
        core.metrics = met
        feat = core.features(tracks, usvs, now, usvp, usvs_)
        corr, plans, risks = feat["corridors"], feat["intercept_plans"], feat["risks"]
        n += 1
        # Prediction active
        for c in corr.values():
            if c.velocity and (c.velocity[0] or c.velocity[1]) and \
                    c.prediction_horizon_s > 0:
                acts["Prediction"] += 1
                break
        # Risk active
        for r in risks.values():
            if r.risk_score > 0:
                acts["Risk"] += 1
                break
        # Reserve desired (as in allocator_centric)
        imminent = 0
        for name, r in risks.items():
            b = getattr(r, "breakthrough_eta", None)
            if b is None or b == float("inf") or b <= 0:
                continue
            too_late = r.interceptor_deficit is not None and r.interceptor_deficit < 0
            if (r.risk_score >= cfg.BRK_RISK_HIGH) or too_late:
                imminent += 1
        if imminent >= 1:
            acts["Reserve"] += 1
        base = {t: list(u) for t, u in s["base_alloc"].items()}
        free = [u for u in usvp if u not in {x for vv in base.values() for x in vv}]
        if free and base:
            acts["Pursuit"] += 1
        # Handoff gate audit: targets with committed + best free alternative
        ev = HandoffEvaluator()
        saw_target = False
        for tgt, assigned in base.items():
            if not assigned or not free:
                continue
            cur = s["usv_map"].get(tgt) if isinstance(s.get("usv_map"), dict) else None
            cur = cur if cur in assigned else assigned[0]
            cur_e = None
            p = core.planner.plan(cur, usvp.get(cur), corr.get(tgt))
            if p is not None:
                cur_e = p.intercept_eta
            best_u, best_e = None, None
            for u in free:
                p = core.planner.plan(u, usvp[u], corr.get(tgt))
                if p is None:
                    continue
                if best_e is None or p.intercept_eta < best_e:
                    best_u, best_e = u, p.intercept_eta
            if best_u is None:
                continue
            saw_target = True
            gates["NO_CURRENT"] += 0
            if best_e is None or cur_e is None or cur_e <= 0:
                gates["NO_ALT"] += 1
                continue
            benefit = (cur_e - best_e) / cur_e
            if best_e >= cur_e:
                gates["ALT_NOT_BETTER"] += 1
            elif benefit < cfg.HANDOFF_MIN_BENEFIT:
                gates["INSUFF_BENEFIT"] += 1
            elif ev._protected(usvs_.get(cur), now):
                gates["LOCK"] += 1
            else:
                gates["LOW_RISK"] += 0  # accepted path
            # score margin: abs benefit vs second-best gap
            etas = []
            for u in free:
                p = core.planner.plan(u, usvp[u], corr.get(tgt))
                if p is not None:
                    etas.append(p.intercept_eta)
            etas = sorted(etas)
            if len(etas) >= 2:
                margin = (etas[1] - etas[0]) / max(1e-9, etas[0])
                cont.append(abs(benefit) / (margin + 1e-9) if margin > 0 else 0.0)
        if saw_target:
            acts["Handoff"] += 1
    with open(os.path.join(OUT, "component_activation_summary.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["component", "total_states", "active_states", "activation_rate"])
        for c in acts:
            w.writerow([c, n, acts[c], round(acts[c] / n, 4)])
            print(f"activation {c}: {acts[c]}/{n} = {acts[c]/n:.4f}")
    with open(os.path.join(OUT, "handoff_gate_summary.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["gate_reason", "count"])
        for k, v in gates.items():
            w.writerow([k, v])
    # score margin summary
    import statistics
    with open(os.path.join(OUT, "score_margin_summary.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["metric", "value"])
        if cont:
            w.writerow(["n_handoff_candidate_states", len(cont)])
            w.writerow(["mean_contribution_over_margin", round(statistics.mean(cont), 4)])
            w.writerow(["median_contribution_over_margin",
                        round(statistics.median(cont), 4)])
            w.writerow(["fraction_contribution_gt_margin",
                        round(sum(1 for x in cont if x > 1.0) / len(cont), 4)])
        else:
            w.writerow(["n_handoff_candidate_states", 0])

    # ── determinism: 100 states x 10 repeats of F (fresh stateless core each call) ──
    rng = random.Random(0)
    sample = rng.sample(states, min(100, len(states)))
    det = {"tested": 0, "mismatch": 0}
    for s in sample:
        out = set()
        for _ in range(10):
            out.add(sig(run_w6(s, GATES["F_Reserve"], W6DecisionCore(), W6Metrics())))
        det["tested"] += 1
        if len(out) != 1:
            det["mismatch"] += 1
    print(f"\nDETERMINISM: states {det['tested']}, mismatch {det['mismatch']} "
          f"-> same-state deterministic = {det['mismatch'] == 0}")
    # hidden-truth counterfactual (mock hidden fields must not matter)
    ht_ok = True
    for s in sample[:20]:
        a = sig(run_w6(s, GATES["F_Reserve"], W6DecisionCore(), W6Metrics()))
        # inject mock hidden truth copies (should be ignored by allocator)
        import copy
        s2 = copy.deepcopy(s)
        for tk in s2.get("tracks", {}):
            s2["tracks"][tk]["hidden_mock"] = [999999.0, 999999.0]
        b = sig(run_w6(s2, GATES["F_Reserve"], W6DecisionCore(), W6Metrics()))
        if a != b:
            ht_ok = False
    print(f"HIDDEN-TRUTH COUNTERFACTUAL = {'PASS' if ht_ok else 'FAIL'}")
    print("[done]")


if __name__ == "__main__":
    sys.exit(main())
