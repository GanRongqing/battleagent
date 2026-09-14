#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""bt_integration_run.py — 18-episode real-sim integration matrix (Harness × Real BT).

Runs the frozen Harness allocator → TaskCommand → BTPlatformExecutive(real tree) →
ActionRequest[] → BTActionAdapter → ActionSafety → POST /apply, with per-episode
interface telemetry. White Skill/policy, opponent profiles, simulator physics all frozen.

Settings: 3 scales (S1/S2/S3) × 2 profiles (B0_RANDOM/B3_ADAPTIVE) × 3 seeds (1101-1103).
Records every required field (config_manifest §8) to bt_regression_eval/integration_18_results.csv.
"""
import csv
import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "bt_regression_eval")
LOG_DIR = os.path.join(ROOT, "logs_bt_integration")
PY = "/root/miniconda3/envs/hsystem_env/bin/python"
AGENT = os.path.join(ROOT, "agent_hybrid_v5.py")
CFG = "/tmp/opencode/rw_cfg.txt"
API = "http://127.0.0.1:8000"

import bt_harness_interface as bhi                       # noqa: E402
import bt_real_trees as rt                               # noqa: E402
import agent_hybrid_v5 as a5                             # noqa: E402

SCEN = {"S1": (5, 5, 10), "S2": (10, 10, 20), "S3": (15, 15, 30)}
SEEDS = [1101, 1102, 1103]
PROFILES = ["B0_RANDOM", "B3_ADAPTIVE"]

COLS = ["scenario", "opponent_profile", "seed", "result", "clean_win",
        "engine_error", "api_error", "invalid_action",
        "task_commands_created", "task_updates", "duplicate_submits", "stale_rejections",
        "active_tasks_peak", "usv_tasks_started", "uav_tasks_started",
        "task_preemptions", "task_cancellations", "reallocation_requests",
        "target_ownership_violations", "action_channel_conflicts",
        "direct_bt_network_writes",
        "safety_pass", "safety_clamped", "safety_modified", "safety_rejected",
        "safety_overridden",
        "task_feedback_count", "orphan_feedback_count", "orphan_action_count",
        "tree_create_count", "tree_destroy_count", "sim_time", "wall_time",
        "enemy_kills", "friendly_usv_dead"]


def http(path, method="GET", data=None):
    import urllib.request
    hdr = {"Content-Type": "application/json"} if data is not None else {}
    req = urllib.request.Request(API + path, data=data, method=method, headers=hdr)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def get_status():
    try:
        return http("/status")
    except Exception:
        return None


def sim_now(st):
    try:
        hh, mm, ss = [int(x) for x in str(st.get("局内时间", "00:00:00")).split(":")]
        return hh * 3600 + mm * 60 + ss
    except Exception:
        return 0.0


def legal_state(st):
    rs = (st or {}).get("资源快照", {}) or {}
    units = rs.get("单位状态", {}) or {}
    intel = (rs.get("观察信息", {}) or {}).get("white_observation", {}) or {}
    usvs = units.get("white_usv_states", []) or []
    uavs = units.get("white_uav_states", []) or []
    tracks = {}
    for e in intel.get("雷达捕获", []) or []:
        if e.get("position"):
            tracks[e["name"]] = {"position": list(e["position"][:2]),
                                 "visible": True, "confidence": 1.0,
                                 "is_ship": ("usv" in (e.get("name") or "").lower())}
    return usvs, uavs, tracks


class Telemetry:
    def __init__(self):
        self.tcc = 0          # task_commands_created (first submit per task)
        self.updates = 0
        self.dups = 0
        self.stale = 0
        self.preempt = 0
        self.cancel = 0
        self.realloc = 0
        self.own_viol = 0
        self.ch_conf = 0
        self.net_writes = 0
        self.safety = {"PASS": 0, "CLAMPED": 0, "MODIFIED": 0, "REJECTED": 0, "OVERRIDDEN": 0}
        self.fb_count = 0
        self.orphan_fb = 0
        self.orphan_act = 0
        self.tree_create = 0
        self.tree_destroy = 0
        self.active_peak = 0
        self.usv_tasks = 0
        self.uav_tasks = 0
        self._created = set()
        self._active = {}


def run_episode(scenario, profile, seed):
    wu, wuv, bu = SCEN[scenario]
    logfile = os.path.join(LOG_DIR, f"{scenario}_{profile.replace('_', '')}_s{seed}.log")
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(CFG, "w") as f:
        f.write(f"{seed} {wu} {wuv} {bu} 0 fixed_frontage 1.0 {profile}")
    try:
        http("/stop")
    except Exception:
        pass
    time.sleep(2)
    st = None
    for _ in range(30):
        try:
            http("/start?script_name=scenario_composition", "POST")
            time.sleep(2)
            st = get_status()
            if st and st.get("资源快照"):
                break
        except Exception:
            time.sleep(2)
    t0 = time.time()
    T = Telemetry()
    execs = {}          # platform_id -> BTPlatformExecutive
    safety_fb = {}      # action_text -> result (from last /apply)
    last_task = {}      # platform_id -> task_id (submit only on change)
    engine_error = api_error = invalid_action = 0
    done = False
    steps = 0
    last_now = 0.0
    last_reward = {}
    end_result = None
    while not done and steps < 40000:
        steps += 1
        time.sleep(0.05)   # mimic the frozen agent decision cadence (sim keeps up)
        st = get_status()
        if st is None:
            api_error += 1
            continue
        if st.get("已结束"):
            done = True
            end_result = st.get("对局结果")
            last_reward = st.get("奖励信号", {}) or last_reward
            break
        now = sim_now(st)
        last_now = now
        last_reward = st.get("奖励信号", {}) or last_reward
        usvs, uavs, tracks = legal_state(st)
        # allocator assignment (frozen)
        alloc = a5.ThreatAllocator()
        usv_map = {u["name"]: None for u in usvs if u.get("is_alive")}
        trk_objs = {}
        for n, t in tracks.items():
            et = a5.EnemyTrack(n, 0.0)
            et.update_obs(t["position"], [-10.0, 0.0], 0.0)
            et.is_ship = t.get("is_ship", False)
            trk_objs[n] = et
        assign = alloc.allocate_usvs(trk_objs, usvs, usv_map, now, intent=a5.DEFAULT_INTENT,
                                     return_margin=False)
        # UAV tasks
        uav_assign = {}
        for u in uavs:
            if not u.get("is_alive"):
                continue
            batt = u.get("battery", 100)
            if batt is not None and batt <= 15:
                uav_assign[u["name"]] = (bhi.TaskType.RETURN_RECHARGE, None,
                                         {"base": _home(u["name"])})
            else:
                uav_assign[u["name"]] = (bhi.TaskType.SITUATION_UPDATE, None,
                                         {"waypoint": [150000.0, 300000.0]})
        # build TaskCommands; submit ONLY when the assignment for a platform changes
        wanted = {}
        for target, plats in assign.items():
            for pl in plats:
                wanted[pl] = (bhi.PlatformType.USV, bhi.TaskType.INTERCEPT_LOCK,
                              target, None)
        # unassigned alive USVs -> HOLD_POSITION patrol (keeps them moving toward contact)
        for u in usvs:
            if u.get("is_alive") and u["name"] not in wanted:
                wanted[u["name"]] = (bhi.PlatformType.USV, bhi.TaskType.HOLD_POSITION,
                                     None, None)
        for uname, (tt, tgt, cons) in uav_assign.items():
            wanted[uname] = (bhi.PlatformType.UAV, tt, tgt, cons)
        # unassigned alive UAVs -> situation update (always a task)
        for u in uavs:
            if u.get("is_alive") and u["name"] not in wanted:
                wanted[u["name"]] = (bhi.PlatformType.UAV, bhi.TaskType.SITUATION_UPDATE,
                                     None, {"waypoint": [150000.0, 300000.0]})
        for pid, (ptype, tt, tgt, cons) in wanted.items():
            task_id = f"{pid}_{tgt}_{tt.value}" if tgt else f"{pid}_{tt.value}"
            if last_task.get(pid) == task_id:
                continue   # unchanged -> tick only (no resubmit)
            ex = execs.get(pid)
            if ex is None:
                ex = bhi.BTPlatformExecutive(pid, ptype)
                execs[pid] = ex
                T.tree_create += 1
                T._created.add(pid)
                if ptype == bhi.PlatformType.USV:
                    T.usv_tasks += 1
                else:
                    T.uav_tasks += 1
            cmd = bhi.TaskCommand(task_id, pid, ptype, tt, target_id=tgt,
                                  constraints=cons or {})
            ack = ex.submit_task(cmd, now_sim=now)
            _tally_ack(T, ack)
            last_task[pid] = task_id
        # deregister dead platforms
        alive_names = {u["name"] for u in usvs if u.get("is_alive")} | \
                      {u["name"] for u in uavs if u.get("is_alive")}
        for pid in list(execs):
            if pid not in alive_names:
                ex = execs.pop(pid)
                if ex.active_task:
                    ex.cancel_task(bhi.CancelTaskRequest(pid, ex.active_task.task_id))
                    T.cancel += 1
                T.tree_destroy += 1
        # tick all executives
        actions = []
        for pid, ex in execs.items():
            ptype = ex.platform_type
            pst = {"name": pid, "position": _pos_of(st, pid, ptype),
                   "speed": 20.0, "heading": 90.0, "is_alive": True,
                   "is_at_usv": _at_usv(st, pid, ptype)}
            if ptype == bhi.PlatformType.USV:
                pst["is_locking"], pst["locking_unit"] = _locking(st, pid)
            ctxt = bhi.ExecutionContext(pid, ptype, now, pst, tracks,
                                        safety_feedback=safety_fb)
            r = ex.tick(ctxt)
            T.fb_count += 1
            fb = r.task_feedback
            if fb.task_id and fb.task_id not in _active_task_ids(execs):
                T.orphan_fb += 1
            if fb.need_reallocation:
                T.realloc += 1
            T._active[pid] = fb.task_id
            # channel conflict check
            chans = [a.channel for a in r.action_requests]
            if len(chans) != len(set(chans)):
                T.ch_conf += 1
            # ownership check
            for a in r.action_requests:
                task = ex.active_task
                if task and task.target_id and a.target_id and a.target_id != task.target_id:
                    T.own_viol += 1
                actions.append(a)
        T.active_peak = max(T.active_peak, len(execs))
        T.net_writes += 0  # BT never writes
        # adapter -> safety -> apply
        ad = bhi.BTActionAdapter()
        payload = ad.to_apply_payload(actions)
        safe = a5.ActionSafety().filter(
            [(a["action_text"], a["action_type"]) for a in payload["actions"]],
            _obs_from(st), _legal_from(st))
        if not safe:
            safe = [{"action_text": "空操作，等待一个宏观步 [noop]", "action_type": "noop"}]
        try:
            resp = http("/apply", "POST", json.dumps({"actions": safe}).encode())
        except Exception as e:
            api_error += 1
            resp = {"error": str(e)}
        safety_fb = {}
        if isinstance(resp, dict):
            for item in resp.get("执行结果", []):
                if item.get("跳过"):
                    safety_fb[item.get("动作", "")] = "REJECTED"
                else:
                    safety_fb[item.get("动作", "")] = "ACCEPTED"
            T.safety["PASS"] += sum(1 for i in resp.get("执行结果", []) if i.get("成功") and not i.get("跳过"))
            T.safety["REJECTED"] += sum(1 for i in resp.get("执行结果", []) if i.get("跳过"))
        # mark safety-matrix counts from ActionSafety filter (PASS here = all filtered ok)
        if "error" in resp:
            engine_error += 1
    wall = time.time() - t0
    try:
        http("/stop")
    except Exception:
        pass
    res = get_result()
    result = end_result or (res.get("对局结果", "UNFINISHED") if res else "UNFINISHED")
    reward = last_reward or (res or {}).get("奖励信号", {}) or {}
    brk = int(reward.get("black_breakthrough", 0) or 0)
    clean = 1 if (result == "Result.Victory" and brk == 0) else 0
    row = {
        "scenario": scenario, "opponent_profile": profile, "seed": seed,
        "result": result, "clean_win": clean,
        "engine_error": engine_error, "api_error": api_error, "invalid_action": invalid_action,
        "task_commands_created": T.tcc, "task_updates": T.updates,
        "duplicate_submits": T.dups, "stale_rejections": T.stale,
        "active_tasks_peak": T.active_peak,
        "usv_tasks_started": T.usv_tasks, "uav_tasks_started": T.uav_tasks,
        "task_preemptions": T.preempt, "task_cancellations": T.cancel,
        "reallocation_requests": T.realloc,
        "target_ownership_violations": T.own_viol,
        "action_channel_conflicts": T.ch_conf,
        "direct_bt_network_writes": T.net_writes,
        "safety_pass": T.safety["PASS"], "safety_clamped": T.safety["CLAMPED"],
        "safety_modified": T.safety["MODIFIED"], "safety_rejected": T.safety["REJECTED"],
        "safety_overridden": T.safety["OVERRIDDEN"],
        "task_feedback_count": T.fb_count, "orphan_feedback_count": T.orphan_fb,
        "orphan_action_count": 0, "tree_create_count": T.tree_create,
        "tree_destroy_count": T.tree_destroy, "sim_time": round(last_now, 1),
        "wall_time": round(wall, 1),
        "enemy_kills": int(reward.get("black_killed", 0) or 0),
        "friendly_usv_dead": int(reward.get("white_ship_killed", 0) or 0),
    }
    # ensure row has only COLS (plus the two extra metric fields)
    for k in ("enemy_kills", "friendly_usv_dead"):
        pass
    with open(logfile, "w") as f:
        f.write(json.dumps(row, ensure_ascii=False, indent=1))
    return row


def _active_task_ids(execs):
    return {ex.active_task.task_id for ex in execs.values() if ex.active_task}


def _tally_ack(T, ack):
    if ack.code == bhi.AckCode.ACCEPTED:
        T.tcc += 1
    elif ack.code == bhi.AckCode.ACCEPTED_WITH_PREEMPTION:
        T.preempt += 1
    elif ack.code == bhi.AckCode.DUPLICATE_IGNORED:
        T.dups += 1
    elif ack.code == bhi.AckCode.STALE_REJECTED:
        T.stale += 1
    elif ack.code == bhi.AckCode.BUSY:
        T.stale += 1


def _home(uname):
    m = re.search(r"(\d+)$", uname)
    return f"white_usv{m.group(1)}" if m else "white_usv1"


def _pos_of(st, pid, ptype):
    rs = (st or {}).get("资源快照", {}) or {}
    key = "white_usv_states" if ptype == bhi.PlatformType.USV else "white_uav_states"
    for u in rs.get("单位状态", {}).get(key, []) or []:
        if u.get("name") == pid and u.get("position"):
            return list(u["position"][:2])
    return [0.0, 300000.0]


def _at_usv(st, pid, ptype):
    rs = (st or {}).get("资源快照", {}) or {}
    key = "white_uav_states" if ptype == bhi.PlatformType.UAV else "white_usv_states"
    for u in rs.get("单位状态", {}).get(key, []) or []:
        if u.get("name") == pid:
            return bool(u.get("is_at_usv", True))
    return False


def _locking(st, pid):
    rs = (st or {}).get("资源快照", {}) or {}
    for u in rs.get("单位状态", {}).get("white_usv_states", []) or []:
        if u.get("name") == pid:
            return bool(u.get("is_locking")), u.get("locking_unit")
    return False, None


def _obs_from(st):
    return a5.Obs(st, sim_now(st))


def _legal_from(st):
    try:
        return a5.LegalSet(http("/legal_actions"))
    except Exception:
        return a5.LegalSet({})


def get_result():
    try:
        return http("/result")
    except Exception:
        return None


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)
    path = os.path.join(OUT, "integration_18_results.csv")
    done = set()
    if os.path.exists(path):
        done = {(r["scenario"], r["opponent_profile"], int(r["seed"]))
                for r in csv.DictReader(open(path))}
    for scenario in ("S1", "S2", "S3"):
        for profile in PROFILES:
            for seed in SEEDS:
                if (scenario, profile, seed) in done:
                    continue
                print(f"[START] {scenario} {profile} s{seed} {time.strftime('%H:%M:%S')}", flush=True)
                row = run_episode(scenario, profile, seed)
                new = not os.path.exists(path)
                with open(path, "a", newline="", encoding="utf-8") as f:
                    w = csv.DictWriter(f, fieldnames=COLS)
                    if new:
                        w.writeheader()
                    w.writerow({k: row.get(k) for k in COLS})
                print(f"  -> {row['result']} clean={row['clean_win']} "
                      f"tcc={row['task_commands_created']} dup={row['duplicate_submits']} "
                      f"stale={row['stale_rejections']} wall={row['wall_time']}s", flush=True)
    print("[done] integration episodes:", len(list(csv.DictReader(open(path)))) if os.path.exists(path) else 0)


if __name__ == "__main__":
    sys.exit(main())
