#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""run_c7_eval.py — C7 (white-combat-0008-v1) hard/control eval + determinism.

Runs the C7 agent per (strategy, seed) via run_agent_wrapper.py, parses [META] outcome, and
recovers lock-conversion metrics from the matching game log (usv_states is_locked/is_locking/
locked_attacker). Legal runtime/log data only — no truth.

Usage:
  python run_c7_eval.py --agent sync --strats W2-1,W2-6,W2-2,W2-4 --seeds 43001,43002,43003,43004,43005
  python run_c7_eval.py --agent sync --strats W2-1 --seeds 43001 --runs 2 --det
"""
import argparse, csv, hashlib, json, os, re, subprocess, time

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "auto_harness", "combat_exchange", "c7_sync_lock")
RAW = os.path.join(OUT, "raw_logs")
GAMES = os.path.join(ROOT, "hsystem", "pomdp_api", "api_logs", "games")
PY = "/root/miniconda3/envs/hsystem_env/bin/python"
SEEDFILE = "/tmp/opencode/seed_w0.txt"
STRATS = {
    "W2-1": "横向编队-中央汇聚箭头突防",
    "W2-2": "菱形编队-接近后扇形展开突防",
    "W2-4": "菱形编队-南北两翼镜像夹击",
    "W2-6": "菱形编队-MUSV外侧绕行SUSV中央收缩",
}
FIELDS = ["Strategy", "Seed", "Valid", "Black_Kills", "White_USV_Losses", "CER", "Exchange_Result",
          "Terminal_Result", "Ever_OwnLock", "Hostile_Locked", "HostileLocked_Never_OwnLock",
          "First_Death_t", "First_OwnLock_t", "Alive_End", "Game_Log"]


def meta(text):
    def g(k):
        m = re.search(rf"\[META\].*?\b{k}=(\S+)", text); return m.group(1) if m else None
    m = re.search(r"\[META\] result=(\S+)", text)
    return {"result": (m.group(1) if m else "UNFINISHED"), "enemy_kills": g("enemy_kills"),
            "friendly_usv_losses": g("friendly_usv_losses"), "friendly_uav_losses": g("friendly_uav_losses")}


def lock_metrics(logpath):
    d = json.load(open(logpath, encoding="utf-8"))
    ever_lock, ever_locked, alive_end = set(), set(), 0
    first_death = None
    first_ownlock = None
    for st in d.get("steps", []):
        t = st.get("episode_time")
        for u in st.get("usv_states", []) or []:
            nm = u.get("name")
            if u.get("is_locking"):
                ever_lock.add(nm)
                if first_ownlock is None:
                    first_ownlock = t
            if u.get("is_locked") or (u.get("locked_attacker") or []):
                ever_locked.add(nm)
            if u.get("is_alive") is False and first_death is None:
                first_death = t
    alive_end = sum(1 for u in (d.get("steps", [{}])[-1].get("usv_states", []) or []) if u.get("is_alive"))
    return {"Ever_OwnLock": len(ever_lock), "Hostile_Locked": len(ever_locked),
            "HostileLocked_Never_OwnLock": len(ever_locked - ever_lock),
            "First_Death_t": first_death, "First_OwnLock_t": first_ownlock, "Alive_End": alive_end,
            "_hash": [hashlib.sha256(json.dumps([[u.get("name"), u.get("is_alive"),
                       u.get("is_locked"), u.get("is_locking")] for u in st.get("usv_states", [])],
                       sort_keys=True).encode()).hexdigest()[:12] for st in d.get("steps", [])]}


def newest_log(scen, t0):
    best, bt = None, 0
    for f in os.listdir(GAMES):
        if not f.endswith(".json"):
            continue
        p = os.path.join(GAMES, f)
        if os.path.getmtime(p) < t0:
            continue
        try:
            if json.load(open(p, encoding="utf-8")).get("script_name") == scen and os.path.getmtime(p) > bt:
                best, bt = p, os.path.getmtime(p)
        except Exception:
            pass
    return best


def _api_get(path, port):
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=15) as r:
            return json.loads(r.read().decode() or "{}")
    except Exception:
        return {}


def _ensure_idle(port):
    for _ in range(30):
        _api_get("/stop", port)
        time.sleep(1.0)
        st = _api_get("/status", port)
        if isinstance(st, dict) and ("未启动" in json.dumps(st, ensure_ascii=False) or st.get("等待指令")):
            return True
    return False


def run_one(sid, scen, seed, port, agent):
    logf = os.path.join(RAW, f"C7_{sid}_seed{seed}.log")
    _ensure_idle(port)
    open(SEEDFILE, "w").write(str(seed))
    env = dict(os.environ); env["SCENARIO_SCRIPT"] = scen; env["LLM_ENABLED"] = "false"
    env["PYTHONUNBUFFERED"] = "1"
    t0 = time.time()
    with open(logf, "w") as f:
        p = subprocess.Popen([PY, "run_agent_wrapper.py", str(port), agent], cwd=ROOT, env=env,
                             stdout=f, stderr=subprocess.STDOUT); p.wait()
    text = open(logf, encoding="utf-8", errors="replace").read(); m = meta(text)
    valid = "[META]" in text
    k = int(m["enemy_kills"]) if m["enemy_kills"] else 0
    l = int(m["friendly_usv_losses"]) if m["friendly_usv_losses"] else 0
    gl = newest_log(scen, t0 - 5)
    lm = lock_metrics(gl) if gl else {kk: "" for kk in
         ("Ever_OwnLock", "Hostile_Locked", "HostileLocked_Never_OwnLock", "First_Death_t",
          "First_OwnLock_t", "Alive_End")}
    row = {"Strategy": sid, "Seed": seed, "Valid": valid, "Black_Kills": k, "White_USV_Losses": l,
           "CER": (round(k / l, 3) if l else ("K:0" if k == 0 else "inf")),
           "Exchange_Result": ("EXCHANGE_WIN" if k > l else ("EXCHANGE_TIE" if k == l else "EXCHANGE_LOSS")),
           "Terminal_Result": m["result"], "Game_Log": os.path.basename(gl) if gl else ""}
    row.update({kk: lm[kk] for kk in ("Ever_OwnLock", "Hostile_Locked", "HostileLocked_Never_OwnLock",
                                      "First_Death_t", "First_OwnLock_t", "Alive_End")})
    return row, lm.get("_hash", [])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", default="sync")
    ap.add_argument("--strats", default="W2-1,W2-6,W2-2,W2-4")
    ap.add_argument("--seeds", default="43001,43002,43003,43004,43005")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--det", action="store_true")
    a = ap.parse_args()
    os.makedirs(RAW, exist_ok=True)
    rows = []
    hashes = {}
    for sid in [s.strip() for s in a.strats.split(",") if s.strip()]:
        for seed in [int(s) for s in a.seeds.split(",") if s.strip()]:
            for r in range(a.runs):
                row, h = run_one(sid, STRATS[sid], seed, a.port, a.agent)
                print(json.dumps(row, ensure_ascii=False), flush=True)
                if a.det:
                    hashes.setdefault((sid, seed), []).append(h)
                if r == 0:
                    rows.append(row)
            with open(os.path.join(OUT, "10_C7_EPISODES.csv"), "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
    if a.det:
        for (sid, seed), hs in hashes.items():
            ok = len(hs) == 2 and hs[0] == hs[1]
            print(f"[DET] {sid} seed{seed} identical={ok}", flush=True)
    print("DONE", len(rows))


if __name__ == "__main__":
    main()
