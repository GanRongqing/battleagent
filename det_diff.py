#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""det_diff.py — STAGE A: field-level + entity-level diff across same-seed runs.

Flattens each captured /status snapshot into {(entity, field): value} and finds the FIRST
divergence (earliest sim-time boundary, then entity, then field) across runs.

Usage: python det_diff.py <traces_dir> <outdir>
"""
import csv
import json
import os
import sys

TR = sys.argv[1] if len(sys.argv) > 1 else "auto_harness/determinism_residual/traces"
OUT = sys.argv[2] if len(sys.argv) > 2 else "auto_harness/determinism_residual"
RUNS = ["run0", "run1", "run2"]
BOUND = ["state_t000.json", "state_t030.json", "state_t060.json"]
BOUND_T = {"state_t000.json": 0.0, "state_t030.json": 30.0, "state_t060.json": 60.0}


def _units(st):
    return ((st or {}).get("资源快照", {}) or {}).get("单位状态", {}) or {}


def flatten(st):
    """-> {(entity, field): value}"""
    flat = {}
    if not isinstance(st, dict):
        return flat
    rs = st.get("资源快照", {}) or {}
    for k, v in (rs.get("统计", {}) or {}).items():
        flat[("stats", k)] = v
    us = _units(st)
    for grp in ("white_usv_states", "white_uav_states"):
        for u in us.get(grp, []) or []:
            nm = u.get("name", "?")
            for f, val in u.items():
                if f == "name":
                    continue
                flat[(nm, f)] = val
    # radar contacts: key by target name if present else index
    obs = (rs.get("观察信息", {}) or {}).get("white_observation", {}) or {}
    for contact_field in ("雷达捕获", "被动告警"):
        for i, c in enumerate(obs.get(contact_field, []) or []):
            key = c.get("name") or c.get("目标") or c.get("target") or f"#{i}"
            for f, val in c.items():
                flat[(f"obs:{contact_field}:{key}", f)] = val
    rw = st.get("奖励信号")
    if isinstance(rw, dict):
        for rk, rv in rw.items():
            flat[("reward", rk)] = rv
    return flat


def load(run, bound):
    p = os.path.join(TR, run, bound)
    if not os.path.exists(p):
        return None
    return json.load(open(p, encoding="utf-8"))


def canon(v):
    return json.dumps(v, ensure_ascii=False, sort_keys=True)


def main():
    os.makedirs(OUT, exist_ok=True)
    first_div = None
    field_rows = []
    entity_rows = []
    per_bound = {}
    for bound in BOUND:
        flats = {}
        for r in RUNS:
            st = load(r, bound)
            flats[r] = flatten(st)
        keys = sorted(set().union(*[set(f.keys()) for f in flats.values()]))
        n_diff = 0
        entities = {}
        for k in keys:
            vals = [canon(flats[r].get(k, "__MISSING__")) for r in RUNS]
            if len(set(vals)) > 1:
                n_diff += 1
                ent, fld = k
                entities.setdefault(ent, []).append(fld)
                field_rows.append({"bound_t": BOUND_T[bound], "entity": ent, "field": fld,
                                   "run0": vals[0][:120], "run1": vals[1][:120], "run2": vals[2][:120]})
        per_bound[bound] = n_diff
        for e, fs in entities.items():
            entity_rows.append({"bound_t": BOUND_T[bound], "entity": e, "n_diff_fields": len(fs),
                                "fields": ";".join(sorted(fs)[:12])})
        if first_div is None and n_diff > 0:
            # earliest field in sorted order
            fr = field_rows[0]
            first_div = {"bound": bound, "sim_time": BOUND_T[bound],
                         "first_entity": fr["entity"], "first_field": fr["field"],
                         "run0": fr["run0"], "run1": fr["run1"], "run2": fr["run2"],
                         "n_diff_fields_total": n_diff,
                         "entities_with_diff": sorted(entities.keys())[:20]}
    # t=0 identical?
    t0_same = per_bound.get("state_t000.json", 0) == 0
    result = {"runs": RUNS, "bounds": BOUND,
              "t0_state_identical": t0_same,
              "diff_counts_per_bound": per_bound,
              "first_divergence": first_div}
    with open(os.path.join(OUT, "01_FIRST_DIVERGENCE.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    with open(os.path.join(OUT, "02_FIELD_DIFF.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["bound_t", "entity", "field", "run0", "run1", "run2"])
        w.writeheader(); w.writerows(field_rows)
    with open(os.path.join(OUT, "03_ENTITY_DIFF.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["bound_t", "entity", "n_diff_fields", "fields"])
        w.writeheader(); w.writerows(entity_rows)
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
