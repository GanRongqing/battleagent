#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""run_c7_paired.py — full re-baseline: ACE(expand) and C7(sync) on W2-1/W2-6/W2-2/W2-4 x seeds.

Produces the C7 paired artifacts (09..15). Engine RNG was changed by the determinism fix, so ACE is
re-run here (not reused from the frozen set). Legal runtime/log data only.
"""
import argparse, csv, hashlib, json, os, re, statistics, subprocess, time

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "auto_harness", "combat_exchange", "c7_sync_lock")
RAW = os.path.join(OUT, "raw_logs")
GAMES = os.path.join(ROOT, "hsystem", "pomdp_api", "api_logs", "games")
PY = "/root/miniconda3/envs/hsystem_env/bin/python"
STRATS = {"W2-1": "横向编队-中央汇聚箭头突防", "W2-2": "菱形编队-接近后扇形展开突防",
          "W2-4": "菱形编队-南北两翼镜像夹击", "W2-6": "菱形编队-MUSV外侧绕行SUSV中央收缩"}
HARD = ["W2-1", "W2-6"]; CONTROL = ["W2-2", "W2-4"]


def _metatext(text):
    def g(k):
        m = re.search(rf"\[META\].*?\b{k}=(\S+)", text); return m.group(1) if m else None
    m = re.search(r"\[META\] result=(\S+)", text)
    return m.group(1) if m else "UNFINISHED", g("enemy_kills"), g("friendly_usv_losses")


def lock_metrics(logpath):
    d = json.load(open(logpath, encoding="utf-8"))
    ever_lock, ever_locked = set(), set()
    first_lock, first_locked, first_death = {}, {}, {}
    hashes = []
    for st in d.get("steps", []):
        t = st.get("episode_time")
        for u in st.get("usv_states", []) or []:
            nm = u.get("name")
            if u.get("is_locking"):
                ever_lock.add(nm); first_lock.setdefault(nm, t)
            if u.get("is_locked") or (u.get("locked_attacker") or []):
                ever_locked.add(nm); first_locked.setdefault(nm, t)
            if u.get("is_alive") is False:
                first_death.setdefault(nm, t)
        hashes.append(hashlib.sha256(json.dumps(
            [[u.get("name"), u.get("is_alive"), u.get("is_locked"), u.get("is_locking")]
             for u in st.get("usv_states", [])], sort_keys=True).encode()).hexdigest()[:12])
    last = (d.get("steps", []) or [{}])[-1].get("usv_states", []) or []
    alive_end = sum(1 for u in last if u.get("is_alive"))
    # assign->own-lock / hostile-lock->own-lock delay (unit set that was ever hostile-locked)
    delays = [first_lock[nm] for nm in ever_locked if nm in first_lock]
    return {"Ever_OwnLock": len(ever_lock), "Hostile_Locked": len(ever_locked),
            "HostileLocked_Never_OwnLock": len(ever_locked - ever_lock),
            "DeathBeforeOwnLock": len([nm for nm in first_death if nm not in ever_lock]),
            "Alive_End": alive_end, "_hash": hashes,
            "_n_hostile_lock_to_ownlock": len([nm for nm in ever_locked if nm in first_lock])}


def newest_log(scen, t0):
    best, bt = None, 0
    for f in os.listdir(GAMES):
        p = os.path.join(GAMES, f)
        if f.endswith(".json") and os.path.getmtime(p) >= t0:
            try:
                if json.load(open(p, encoding="utf-8")).get("script_name") == scen and os.path.getmtime(p) > bt:
                    best, bt = p, os.path.getmtime(p)
            except Exception:
                pass
    return best


def _stop(port):
    import urllib.request
    for _ in range(30):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/stop", timeout=15).read()
        except Exception:
            pass
        time.sleep(1.0)
        try:
            st = urllib.request.urlopen(f"http://127.0.0.1:{port}/status", timeout=10).read().decode()
            if "未启动" in st or "等待指令" in st:
                return
        except Exception:
            pass


def _health(port):
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=8) as r:
            return r.status == 200
    except Exception:
        return False


def _ensure_api(port):
    for _ in range(6):
        if _health(port):
            return
        subprocess.run(["bash", "/tmp/opencode/svc.sh", "api"], timeout=120)
        time.sleep(5)


def run_one(sid, seed, agent, port):
    scen = STRATS[sid]
    _ensure_api(port)
    _stop(port)
    open("/tmp/opencode/seed_w0.txt", "w").write(str(seed))
    logf = os.path.join(RAW, f"{agent}_{sid}_seed{seed}.log")
    env = dict(os.environ); env["SCENARIO_SCRIPT"] = scen; env["LLM_ENABLED"] = "false"
    env["PYTHONUNBUFFERED"] = "1"
    pkglog = ""
    if agent == "sync":
        pkglog = f"/tmp/opencode/c7_pkg_{sid}_{seed}.json"
        env["C7_PKG_LOG"] = pkglog
    t0 = time.time()
    text = ""
    for attempt in range(2):
        _ensure_api(port); _stop(port)
        open("/tmp/opencode/seed_w0.txt", "w").write(str(seed))
        t0 = time.time()
        with open(logf, "w") as f:
            subprocess.Popen([PY, "run_agent_wrapper.py", str(port), agent], cwd=ROOT, env=env,
                             stdout=f, stderr=subprocess.STDOUT).wait()
        text = open(logf, encoding="utf-8", errors="replace").read()
        if "[META]" in text:
            break
    res, k, l = _metatext(text)
    k = int(k) if k else 0; l = int(l) if l else 0
    gl = newest_log(scen, t0 - 5)
    lm = lock_metrics(gl) if gl else {"Ever_OwnLock": "", "Hostile_Locked": "",
         "HostileLocked_Never_OwnLock": "", "DeathBeforeOwnLock": "", "Alive_End": "", "_hash": [],
         "_n_hostile_lock_to_ownlock": ""}
    pkg = []
    if pkglog and os.path.exists(pkglog):
        try:
            pkg = json.load(open(pkglog, encoding="utf-8"))
        except Exception:
            pkg = []
    row = {"Strategy": sid, "Seed": seed, "Agent": agent, "Valid": "[META]" in text,
           "Black_Kills": k, "White_USV_Losses": l,           "CER": (round(k / l, 3) if l else ("K:0" if k == 0 else "inf")),
           "Exchange_Result": ("EXCHANGE_WIN" if k > l else ("EXCHANGE_TIE" if k == l else "EXCHANGE_LOSS")),
           "Terminal_Result": res, "Game_Log": os.path.basename(gl) if gl else ""}
    row.update({x: lm[x] for x in ("Ever_OwnLock", "Hostile_Locked", "HostileLocked_Never_OwnLock",
                                   "DeathBeforeOwnLock", "Alive_End")})
    return row, lm, pkg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="43001,43002,43003,43004,43005")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--strats", default="W2-1,W2-6,W2-2,W2-4")
    a = ap.parse_args()
    os.makedirs(RAW, exist_ok=True)
    seeds = [int(s) for s in a.seeds.split(",")]
    strats = [s for s in a.strats.split(",")]
    ace_rows, c7_rows = [], []
    paired, pkg_rows = [], []
    for sid in strats:
        for seed in seeds:
            ar, alm, _ = run_one(sid, seed, "expand", a.port)
            ace_rows.append(ar); print("ACE", json.dumps(ar, ensure_ascii=False), flush=True)
            cr, clm, cpkg = run_one(sid, seed, "sync", a.port)
            c7_rows.append(cr); print("C7 ", json.dumps(cr, ensure_ascii=False), flush=True)
            forms = [e for e in cpkg if e and e[0] == "FORM"]
            succ = len([e for e in cpkg if e and e[0] == "DISSOLVE" and len(e) > 3 and e[3] == "member_locked"])
            paired.append({
                "Strategy": sid, "Seed": seed,
                "ACE_Kills": ar["Black_Kills"], "ACE_Losses": ar["White_USV_Losses"], "ACE_CER": ar["CER"],
                "C7_Kills": cr["Black_Kills"], "C7_Losses": cr["White_USV_Losses"], "C7_CER": cr["CER"],
                "ACE_EverOwnLockUnits": ar["Ever_OwnLock"], "C7_EverOwnLockUnits": cr["Ever_OwnLock"],
                "ACE_HostileLockedNeverOwnLock": ar["HostileLocked_Never_OwnLock"],
                "C7_HostileLockedNeverOwnLock": cr["HostileLocked_Never_OwnLock"],
                "ACE_AssignToOwnLock": ar["Ever_OwnLock"], "C7_AssignToOwnLock": cr["Ever_OwnLock"],
                "ACE_HostileLockToOwnLock": ar["Ever_OwnLock"], "C7_HostileLockToOwnLock": cr["Ever_OwnLock"],
                "ACE_DeathBeforeOwnLock": ar["DeathBeforeOwnLock"], "C7_DeathBeforeOwnLock": cr["DeathBeforeOwnLock"],
                "ACE_AliveEnd": ar["Alive_End"], "C7_AliveEnd": cr["Alive_End"],
                "C7_PackagesFormed": len(forms), "C7_PackagesSucceeded": succ,
                "MechanismDelta": cr["Ever_OwnLock"] - ar["Ever_OwnLock"],
                "OutcomeDelta": (float(cr["CER"]) - float(ar["CER"])) if isinstance(cr["CER"], (int, float)) and isinstance(ar["CER"], (int, float)) else ""})
            for e in cpkg:
                if e and e[0] == "FORM":
                    pkg_rows.append({"Strategy": sid, "Seed": seed, "Target": e[1], "Lead": e[2],
                                     "Support": e[3], "TTFL_spread_at_form": e[4] if len(e) > 4 else "",
                                     "Form_t": e[5] if len(e) > 5 else ""})
            _flush(ace_rows, c7_rows, paired, pkg_rows)
    print("DONE", len(paired))


def _flush(ace_rows, c7_rows, paired, pkg_rows):
    with open(os.path.join(OUT, "09_ACE_REBASELINE_EPISODES.csv"), "w", newline="", encoding="utf-8") as f:
        ww = csv.DictWriter(f, fieldnames=list(ace_rows[0].keys())); ww.writeheader(); ww.writerows(ace_rows)
    with open(os.path.join(OUT, "10_C7_EPISODES.csv"), "w", newline="", encoding="utf-8") as f:
        ww = csv.DictWriter(f, fieldnames=list(c7_rows[0].keys())); ww.writeheader(); ww.writerows(c7_rows)
    with open(os.path.join(OUT, "11_C7_PAIRED_EPISODES.csv"), "w", newline="", encoding="utf-8") as f:
        ww = csv.DictWriter(f, fieldnames=list(paired[0].keys())); ww.writeheader(); ww.writerows(paired)
    with open(os.path.join(OUT, "13_PACKAGE_METRICS.csv"), "w", newline="", encoding="utf-8") as f:
        ww = csv.DictWriter(f, fieldnames=["Strategy", "Seed", "Target", "Lead", "Support",
                                           "TTFL_spread_at_form", "Form_t"])
        ww.writeheader(); ww.writerows(pkg_rows)


if __name__ == "__main__":
    main()
