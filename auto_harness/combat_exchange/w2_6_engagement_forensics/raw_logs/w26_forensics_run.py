#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys, os, csv, json
sys.path.insert(0, "/tmp/opencode")
import w26_forensics_lib as L

D = L.D
def w(path, header, rows):
    with open(os.path.join(D, path), "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f); wr.writerow(header); wr.writerows(rows)

# ---------- Stage B: unit timeline + events (seed 43001) ----------
units_rows = []
events_rows = []
for case, path in (("W2-6_ACE", L.e2_path("W2-6", "ACE", 43001)),
                   ("W2-6_C10", L.c10_path("W2-6", 43001)),
                   ("W2-4_ACE", L.e2_path("W2-4", "ACE", 43001))):
    d = L.load(path)
    U, conc = L.per_unit(d)
    for n in sorted(U, key=lambda x: int(x.split("usv")[-1])):
        uu = U[n]
        units_rows.append([case, n, uu["first_contact"], uu["first_inrange"], uu["first_hostile_lock"],
                           len(uu["hits"]), uu["first_own"], uu["death"],
                           "YES" if uu["ever_own"] else "NO",
                           "YES" if (uu["death"] is not None and (not uu["ever_own"] or uu["death"] < uu["first_own"])) else "NO",
                           "|".join(sorted(uu["locked_attacker"]))])
        if uu["death"] is not None:
            events_rows.append([case, n, uu["death"], "DEATH", f"own_lock={'Y' if uu['ever_own'] else 'N'}",
                                f"hits={len(uu['hits'])}", "usv_states.is_alive", "game_log"])
        for h in uu["hits"]:
            events_rows.append([case, n, h, "INCOMING_HIT", f"by={','.join(sorted(uu['locked_attacker']))}",
                                f"index={uu['hits'].index(h)+1}", "usv_states.locked_times", "game_log"])
        if uu["first_own"] is not None:
            events_rows.append([case, n, uu["first_own"], "FIRST_OWN_LOCK", "", "",
                                "usv_states.is_locking", "game_log"])
w("03_W2_6_UNIT_TIMELINE.csv",
  ["case", "unit", "first_contact", "first_inrange", "first_hostile_lock", "incoming_hits", "first_own_lock",
   "death", "ever_own_lock", "prelock_death", "hostile_lockers"], units_rows)
w("04_W2_6_ENGAGEMENT_EVENTS.csv",
  ["case", "unit", "sim_time", "event", "detail", "detail2", "source_field", "source"], events_rows)

# ---------- Stage C: concurrency time series + metrics ----------
conc_rows = []
mets = {}
for case, path in (("W2-6_ACE", L.e2_path("W2-6", "ACE", 43001)),
                   ("W2-6_C10", L.c10_path("W2-6", 43001)),
                   ("W2-4_ACE", L.e2_path("W2-4", "ACE", 43001))):
    m = L.metrics(path); mets[case] = m
    for t, c, inr in m["conc"]:
        conc_rows.append([case, t, c, inr])
w("05_CONCURRENT_LOCK_TIMESERIES.csv", ["case", "sim_time", "concurrent_own_locks", "in_range_units"], conc_rows)

# interruption analysis
intr_rows = []
for case, path in (("W2-6_ACE", L.e2_path("W2-6", "ACE", 43001)),
                   ("W2-6_C10", L.c10_path("W2-6", 43001)),
                   ("W2-4_ACE", L.e2_path("W2-4", "ACE", 43001))):
    m = mets[case]; durs = L.run_durations(m["U"])
    n_runs = len(durs)
    ge300 = len([x for x in durs if x >= 300])
    lt300 = len([x for x in durs if x < 300])
    intr = sum(1 for n in m["U"] for (a, b) in m["U"][n]["own_runs"] if b is not None)  # runs ended
    intr_rows.append([case, n_runs, ge300, lt300, round(sum(durs) / max(1, n_runs), 1),
                      max(durs) if durs else 0, m["sustained_runs"]])
w("06_LOCK_INTERRUPTION_ANALYSIS.csv",
  ["case", "own_lock_runs", "runs_ge_300s", "runs_lt_300s", "mean_run_s", "max_run_s", "sustained_hit_capable_runs"], intr_rows)

# overlap md
with open(os.path.join(D, "07_W2_6_VS_W2_4_OVERLAP.md"), "w", encoding="utf-8") as f:
    f.write("# 07 — W2-6 vs W2-4 CONCURRENT-LOCK OVERLAP (seed 43001)\n\n")
    f.write("| case | max conc | mean conc | unit-lock-time(s) | t(C>=1) | t(C>=2) | t(C>=4) | t(C>=6) | sustained>=300s runs |\n")
    f.write("|---|---|---|---|---|---|---|---|---|\n")
    for c in ("W2-6_ACE", "W2-6_C10", "W2-4_ACE"):
        m = mets[c]
        f.write(f"| {c} | {m['maxc']} | {m['mean_c']} | {m['ulock_time_s']:.0f} | {m['t_lock_ge1']:.0f} | "
                f"{m['t_lock_ge2']:.0f} | {m['t_lock_ge4']:.0f} | {m['t_lock_ge6']:.0f} | {m['sustained_runs']} |\n")
    f.write("\n`C(t)` = #alive White USVs with `is_locking=True` at step t (30 s).\n")

# ---------- Stage D: lock->kill funnel ----------
def K(path_log, case):
    if case.endswith("C10"):
        return int(L.C10RESULTS[("W2-6", "43001")]["Black_Killed"])
    r = next(x for x in L.E2ROWS if x["Strategy"] == case[:4] and x["Policy"] == "ACE" and x["Seed"] == "43001")
    return int(r["Black_Killed"])
frows = []
for case in ("W2-6_ACE", "W2-6_C10"):
    m = mets[case]
    k = 10 if case == "W2-6_ACE" else 11
    frows.append([case, m["own_units"], m["sustained_runs"], round(0.8 * m["sustained_runs"], 1),
                  k, m["prelock"], m["dead"], m["maxc"], m["ulock_time_s"]])
w("08_LOCK_TO_KILL_FUNNEL.csv",
  ["case", "units_ever_own_lock", "sustained_runs_ge300s", "expected_white_hits(0.8*runs)", "black_killed_meta",
   "prelock_deaths", "total_deaths", "max_concurrency", "unit_lock_time_s"], frows)

# ---------- Stage D: target-level (actions -> requested targets; active-lock target NOT_MEASURED) ----------
trows = []
for case, path in (("W2-6_ACE", L.e2_path("W2-6", "ACE", 43001)), ("W2-6_C10", L.c10_path("W2-6", 43001))):
    d = L.load(path)
    req = {}; reqs = 0
    for s in d["steps"]:
        for a in s.get("actions") or []:
            t = a.get("动作", "")
            if "锁定" in t and "被锁定" not in t:
                reqs += 1
                unit = t.split(" ")[0]; tgt = t.split("锁定")[-1].strip()
                req.setdefault(tgt, set()).add(unit)
    trows.append([case, reqs, len(req), ";".join(f"{k}:{len(v)}" for k, v in sorted(req.items())[:12]),
                  "NOT_MEASURED(active-lock target not in usv_states)"])
w("09_TARGET_LEVEL_ENGAGEMENT.csv",
  ["case", "lock_request_actions", "distinct_requested_targets", "targets_by_#requesting_units", "active_lock_target"], trows)

# ---------- Stage E: white survival timeline ----------
srows = []
for case, path in (("W2-6_ACE", L.e2_path("W2-6", "ACE", 43001)), ("W2-6_C10", L.c10_path("W2-6", 43001))):
    d = L.load(path); U, conc = L.per_unit(d)
    alive_prev = None
    for t, c, inr in conc:
        step_alive = None
    # death timeline
    deaths = sorted([(U[n]["death"], n) for n in U if U[n]["death"] is not None])
    own_at = {}
    for n in U:
        if U[n]["first_own"] is not None:
            own_at[n] = U[n]["first_own"]
    first_own_all = min(own_at.values()) if own_at else None
    rows_pts = [(0, 20)]
    for n in U: pass
    # compute alive over time from conc length? recompute quickly
    s = d["steps"]
    alive0 = sum(1 for u in s[0]["usv_states"] if u.get("is_alive"))
    def alive_at(t):
        # nearest step
        best = None
        for ss in s:
            h, m, sec = ss["episode_time"].split(":"); tt = int(h)*3600+int(m)*60+float(sec)
            if best is None or abs(tt - t) < best[0]:
                best = (abs(tt - t), sum(1 for u in ss["usv_states"] if u.get("is_alive")))
        return best[1] if best else None
    for dt, n in deaths:
        srows.append([case, n, dt, "death", f"alive_after={alive_at(dt)}",
                      f"own_lock_at={own_at.get(n,'NONE')}"])
    srows.append([case, "-", first_own_all, "first_own_lock_of_force", f"alive_at={alive_at(first_own_all)}" if first_own_all else "", ""])
    fd = min((U[n]["death"] for n in U if U[n]["death"] is not None), default=None)
    srows.append([case, "-", fd, "first_death", "", ""])
w("10_WHITE_SURVIVAL_TIMELINE.csv", ["case", "unit", "sim_time", "event", "alive_state", "own_lock_state"], srows)
print("Stage B/C/D/E CSVs written")
print("metrics:", {k: {kk: mets[k][kk] for kk in ("maxc", "mean_c", "ulock_time_s", "own_units", "sustained_runs", "prelock", "dead")} for k in mets})
