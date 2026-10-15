#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""W2-6 engagement forensics analyzer (offline; read-only). Produces the w2_6_engagement_forensics CSVs."""
import json, glob, os, csv, math, hashlib
from collections import defaultdict

E2G = "hsystem/pomdp_api/api_logs/games"
D = "auto_harness/combat_exchange/w2_6_engagement_forensics"
STEP = 30.0
E2ROWS = list(csv.DictReader(open("auto_harness/combat_exchange/e2_ace_c7_seed_independent/_e2_rows_private.csv",
                                 newline="", encoding="utf-8")))


def e2_path(strat, pol, seed):
    r = next((x for x in E2ROWS if x["Strategy"] == strat and x["Policy"] == pol and x["Seed"] == str(seed)
              and str(x.get("Valid")) == "True"), None)
    return os.path.join(E2G, r["_Game_Log"]) if r and r.get("_Game_Log") else None


C10RESULTS = {}
for f in glob.glob("/tmp/opencode/parallel_runs/c10eval/results/*.json"):
    rr = json.load(open(f, encoding="utf-8"))["Result"]
    C10RESULTS[(rr["Strategy"], str(rr["Seed"]))] = rr


def c10_path(strat, seed):
    rr = C10RESULTS.get((strat, str(seed)))
    if not rr or str(rr.get("Valid")) not in ("True", "true", True):
        return None
    for w in os.listdir("/tmp/opencode/parallel_runs/c10eval"):
        p = os.path.join("/tmp/opencode/parallel_runs/c10eval", w, "api_logs", "games", rr.get("Game_Log", ""))
        if os.path.exists(p):
            return p
    return None


def load(path):
    return json.load(open(path, encoding="utf-8"))


def per_unit(d):
    """Return per-unit event dict + concurrency series + interruption list."""
    U = {}
    def u(n):
        return U.setdefault(n, {"first_contact": None, "first_inrange": None, "first_hostile_lock": None,
                                "hits": [], "first_own": None, "own_runs": [], "death": None,
                                "lock_interrupts": 0, "ever_own": False, "locked_attacker": set()})
    conc = []          # (t, C(t))
    inrange_series = []
    running = {}       # unit -> current own-run start time
    for s in d["steps"]:
        t = None
        try:
            h, m, sec = s["episode_time"].split(":"); t = int(h) * 3600 + int(m) * 60 + float(sec)
        except Exception:
            t = len(conc) * STEP
        ae = s.get("active_enemies") or []
        pa = s.get("passive_enemies") or []
        c = 0; inr = 0
        alive_names = set()
        for su in s["usv_states"]:
            n = su["name"]
            if not su.get("is_alive"):
                continue
            alive_names.add(n)
            uu = u(n)
            if ae and uu["first_contact"] is None:
                uu["first_contact"] = t
            if pa and uu["first_hostile_lock"] is None and (su.get("is_locked") or su.get("locked_attacker")):
                uu["first_hostile_lock"] = t
            if su.get("is_locked") or su.get("locked_attacker"):
                for a in (su.get("locked_attacker") or []):
                    uu["locked_attacker"].add(a)
                if uu["first_hostile_lock"] is None:
                    uu["first_hostile_lock"] = t
            # in range
            if ae and su.get("position"):
                for e in ae:
                    q = e.get("position")
                    if q and math.hypot(q[0] - su["position"][0], q[1] - su["position"][1]) <= 40000:
                        if uu["first_inrange"] is None:
                            uu["first_inrange"] = t
                        inr += 1; break
            # hits (locked_times increments)
            lt = su.get("locked_times") or 0
            if lt > len(uu["hits"]):
                for _ in range(lt - len(uu["hits"])):
                    uu["hits"].append(t)
            # own lock
            if su.get("is_locking"):
                if not uu["ever_own"]:
                    uu["ever_own"] = True
                    uu["first_own"] = t
                if n not in running:
                    running[n] = t
                c += 1
            else:
                if n in running:
                    uu["own_runs"].append((running.pop(n), t))
        # closing runs for units no longer alive
        for n in list(running):
            if n not in alive_names:
                U[n]["own_runs"].append((running.pop(n), None))
                U[n]["lock_interrupts"] += 0
        # deaths
        for su in s["usv_states"]:
            if su.get("is_alive") is False and U.get(su["name"], {}).get("death") is None:
                u(su["name"])["death"] = t
                if su["name"] in running:
                    U[su["name"]]["own_runs"].append((running.pop(su["name"]), t))
        conc.append((t, c, inr))
    # close dangling runs at end
    for n, st in running.items():
        U[n]["own_runs"].append((st, conc[-1][0] if conc else st))
    return U, conc


def run_durations(U):
    durs = []
    for n, uu in U.items():
        for a, b in uu["own_runs"]:
            if b is None:
                continue
            durs.append(max(0.0, b - a))
    return durs


def metrics(path):
    d = load(path)
    U, conc = per_unit(d)
    C = [c for _, c, _ in conc]
    maxc = max(C) if C else 0
    mean_c = sum(C) / max(1, len(C))
    times = [t for t, _, _ in conc]
    ulock_steps = sum(C)
    sustained = [x for x in run_durations(U) if x >= 300.0 - 1e-6]
    own_units = sum(1 for n in U if U[n]["ever_own"])
    prelock = sum(1 for n in U if U[n]["death"] is not None and (not U[n]["ever_own"] or U[n]["death"] < U[n]["first_own"]))
    dead = sum(1 for n in U if U[n]["death"] is not None)
    hits = sum(len(U[n]["hits"]) for n in U)
    # concurrency overlap times
    def time_ge(k): return sum(STEP for c in C if c >= k)
    return dict(U=U, conc=conc, maxc=maxc, mean_c=round(mean_c, 2), ulock_steps=ulock_steps,
                ulock_time_s=ulock_steps * STEP, own_units=own_units, prelock=prelock, dead=dead,
                hits=hits, sustained_runs=len(sustained),
                t_lock_ge1=time_ge(1), t_lock_ge2=time_ge(2), t_lock_ge4=time_ge(4), t_lock_ge6=time_ge(6),
                first_own=min((U[n]["first_own"] for n in U if U[n]["first_own"] is not None), default=None),
                first_death=min((U[n]["death"] for n in U if U[n]["death"] is not None), default=None))
