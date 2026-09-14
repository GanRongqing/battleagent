#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""dev4_soft_persistence_shadow/persist.py — online persistence state-machine replay.

Reads sequential shadow decision logs (per-decision: platform shadow {p,cur,cur_risk,alt,
alt_risk,near_lock,unique,cov_unsafe,block}). Simulates continuous persistence timers per
(platform,current,alternative). Policies P300/P600/P1200 emit WOULD_EXECUTE once when
continuous trigger duration >= horizon; then measures POST-TRIGGER stability/reversal/
target-switch/lifetime from the frozen trajectory.
"""
import csv
import json
import os
import sys

OUT = os.path.dirname(os.path.abspath(__file__))
HORIZONS = {"P300": 300.0, "P600": 600.0, "P1200": 1200.0}


def load(path):
    recs = []
    for l in open(path):
        try:
            recs.append(json.loads(l))
        except Exception:
            pass
    recs.sort(key=lambda r: (r["episode"], r["sim_time"]))
    return recs


def run(path, label):
    recs = load(path)
    per_ep = {}
    for r in recs:
        per_ep.setdefault(r["episode"], []).append(r)
    # timeline of trigger states per platform per decision
    events = {h: [] for h in HORIZONS}
    for ep, evs in per_ep.items():
        trig = []   # list of dicts per decision
        for r in evs:
            t = r["sim_time"]
            m = {}
            for s in r.get("shadows", []):
                if s.get("block") == "PROPOSAL":
                    m[s["p"]] = (s["cur"], s["alt"], s["cur_risk"], s["alt_risk"])
            trig.append((t, m))
        # state machine per identity
        active = {}   # (p,cur,alt) -> {"start":t,"emit":{h:False}, "last":t}
        prev_t = None
        for (t, m) in trig:
            # mark identities present this decision
            seen = set()
            for (p, (cur, alt, cr, ar)) in m.items():
                ident = (p, cur, alt)
                seen.add(ident)
                if ident in active:
                    if prev_t is not None and (t - prev_t) > 60.0:
                        # gap -> reset (shouldn't happen w/ continuous decisions)
                        active.pop(ident, None)
                    else:
                        active[ident]["last"] = t
                else:
                    active[ident] = {"start": t, "last": t, "emit": {h: False for h in HORIZONS}}
            # expire identities not seen this decision
            for ident in list(active.keys()):
                if ident not in seen:
                    active.pop(ident, None)
            # check horizons for each active identity
            for ident, st in list(active.items()):
                dur = t - st["start"]
                for h, hv in HORIZONS.items():
                    if dur >= hv and not st["emit"][h]:
                        st["emit"][h] = True
                        events[h].append({"episode": ep, "seed": ep.rsplit("_", 1)[-1],
                                          "opportunity_id": f"{ep}|{ident[0]}|{ident[1]}|{ident[2]}",
                                          "platform": ident[0], "current_target": ident[1],
                                          "alternative_target": ident[2],
                                          "first_seen_time": st["start"],
                                          "would_execute_time": t,
                                          "pre_trigger_duration": round(dur, 1)})
            prev_t = t
    # post-trigger stability using decision timelines
    for h in HORIZONS:
        evs = events[h]
        for e in evs:
            ep = e["episode"]
            tl = per_ep[ep]
            idx = next((i for i, r in enumerate(tl) if r["sim_time"] >= e["would_execute_time"]), None)
            times = [r["sim_time"] for r in tl]
            p, cur, alt = e["platform"], e["current_target"], e["alternative_target"]
            def trig_at(w):
                target = e["would_execute_time"] + w
                i = next((j for j, tt in enumerate(times) if tt >= target), None)
                if i is None:
                    return False
                m = {}
                for s in tl[i].get("shadows", []):
                    if s.get("block") == "PROPOSAL":
                        m[s["p"]] = (s["cur"], s["alt"])
                return m.get(p) == (cur, alt)
            e["post_stable_300"] = trig_at(300)
            e["post_stable_600"] = trig_at(600)
            e["post_stable_1200"] = trig_at(1200)
            # lifetime until first decision (>= exec) where identity not triggered
            lifetime = None
            for i in range(idx if idx is not None else 0, len(tl)):
                r = tl[i]
                m = {}
                for s in r.get("shadows", []):
                    if s.get("block") == "PROPOSAL":
                        m[s["p"]] = (s["cur"], s["alt"])
                if m.get(p) != (cur, alt):
                    lifetime = r["sim_time"] - e["would_execute_time"]
                    break
            if lifetime is None:
                lifetime = times[-1] - e["would_execute_time"] if times else 0.0
            e["post_trigger_lifetime"] = round(lifetime, 1)
            e["post_reversal_300"] = (not e["post_stable_300"] and lifetime < 300)
            e["post_reversal_600"] = (not e["post_stable_600"] and lifetime < 600)
            e["post_reversal_1200"] = (not e["post_stable_1200"] and lifetime < 1200)
            # alternative switch count within windows
            for w, key in ((300, "alt_switch_300"), (600, "alt_switch_600"), (1200, "alt_switch_1200")):
                cnt = 0
                for i in range(idx if idx is not None else 0, len(tl)):
                    r = tl[i]
                    if r["sim_time"] > e["would_execute_time"] + w:
                        break
                    m = {}
                    for s in r.get("shadows", []):
                        if s.get("block") == "PROPOSAL" and s["p"] == p:
                            m[s["p"]] = s["alt"]
                    if m.get(p) and m[p] != alt:
                        cnt += 1
                e[key] = cnt
    return events, label


def write_summary(events, label, per_policy_file, cross_rows):
    rows = []
    for h, evs in events.items():
        n = len(evs)
        s300 = sum(1 for e in evs if e["post_stable_300"])
        s600 = sum(1 for e in evs if e["post_stable_600"])
        s1200 = sum(1 for e in evs if e["post_stable_1200"])
        r300 = sum(1 for e in evs if e["post_reversal_300"])
        lif = sorted(e["post_trigger_lifetime"] for e in evs)
        med = lif[len(lif) // 2] if lif else 0.0
        plats = len({e["platform"] for e in evs})
        atgts = len({e["alternative_target"] for e in evs})
        rows.append([label, h, n, plats, atgts, s300, s600, s1200, r300, med])
        print(f"{label} {h}: would_execute={n} post300={s300} post600={s600} "
              f"post1200={s1200} rev300={r300} med_lifetime={med}")
        cross_rows.setdefault(h, []).append({"label": label, "seed": "*",
                                             "would_execute": n, "post600": s600})
    with open(per_policy_file, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["dataset", "policy", "would_execute", "unique_platforms",
                    "unique_alt_targets", "post_stable_300", "post_stable_600",
                    "post_stable_1200", "reversal_300", "median_post_lifetime"])
        w.writerows(rows)
    return rows


def main():
    p1 = os.path.join(OUT, "..", "dev4_soft_shadow_audit", "shadow.jsonl")
    events1, _ = run(p1, "4001-4003")
    cross = {}
    write_summary(events1, "4001-4003",
                  os.path.join(OUT, "PERSISTENCE_POLICY_SUMMARY_4001_4003.csv"), cross)
    p2 = os.path.join(OUT, "shadow_4004_4006.jsonl")
    if os.path.exists(p2):
        events2, _ = run(p2, "4004-4006")
        write_summary(events2, "4004-4006",
                      os.path.join(OUT, "PERSISTENCE_VALIDATION_4004_4006.csv"), cross)
    # cross-seed (per policy per seed counts)
    with open(os.path.join(OUT, "PERSISTENCE_CROSS_SEED_SUMMARY.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["dataset", "policy", "seeds_with_execute", "total_execute", "post600"])
    # per seed counts from events detail (re-derive quickly by re-run collecting seed)
    for path, lab in ((p1, "4001-4003"), (p2, "4004-4006")):
        if not os.path.exists(path):
            continue
        events, _ = run(path, lab)
        for h, evs in events.items():
            from collections import Counter
            c = Counter(e["seed"] for e in evs)
            s6 = Counter(e["seed"] for e in evs if e["post_stable_600"])
            with open(os.path.join(OUT, "PERSISTENCE_CROSS_SEED_SUMMARY.csv"), "a",
                      newline="") as f:
                w = csv.writer(f)
                for seed in sorted(set(list(c) + list(s6))):
                    w.writerow([lab, h, seed, c.get(seed, 0), s6.get(seed, 0)])
    print("[done]")


if __name__ == "__main__":
    sys.exit(main())
