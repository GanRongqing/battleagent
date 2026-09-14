#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""bt_port_runner.py — 服务器行为树端口驱动（Harness × behavior_tree 端口接入）

与 bt_integration_run.py 同管线结构（ThreatAllocator → TaskCommand → tick →
动作 → ActionSafety → /apply），区别:
  - import 的是 hsystem 根目录下新上传的 behavior_tree 包（不动服务器原有
    bt_harness_interface.py / bt_real_trees.py / bt_integration_run.py）;
  - tick 产出走 BTActionAdapter.to_apply_payload():具体动作
    （action_text/action_type，数值来自树内计算与任务约束，端口无预设值）;
  - 动作经本驱动整批 POST /apply 执行（参数在此输入），回执映射
    safety_feedback 供下一 tick 驱动树推进。

用法（在 hsystem 根目录下）:
  python behavior_tree/bt_port_runner.py                            # S1×B0_RANDOM×3 种子
  python behavior_tree/bt_port_runner.py --scenario S1 --profile B0_RANDOM --seed 1101

依赖: 与 bt_integration_run.py 相同的环境（miniconda hsystem_env），
pomdp_api 需已在 8000 端口启动。
"""
import argparse
import csv
import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # hsystem 根目录
if ROOT not in sys.path:      # behavior_tree 包与 agent_hybrid_v5 同层
    sys.path.insert(0, ROOT)

from behavior_tree.harness_interface import (       # noqa: E402
    AckCode, BTActionAdapter, BTPlatformExecutive, CancelTaskRequest,
    ExecutionContext, PlatformType, TaskCommand, TaskType)
import agent_hybrid_v5 as a5                        # noqa: E402

API = "http://127.0.0.1:8000"
CFG = "/tmp/opencode/bt_port_cfg.txt"        # 独立配置文件，不碰 rw_cfg.txt
LOG_DIR = os.path.join(ROOT, "bt_port_logs")
OUT_DIR = os.path.join(ROOT, "bt_port_eval")

SCEN = {"S1": (5, 5, 10), "S2": (10, 10, 20), "S3": (15, 15, 30)}
SEEDS = [1101, 1102, 1103]
PROFILES = ["B0_RANDOM", "B3_ADAPTIVE"]

COLS = ["scenario", "opponent_profile", "seed", "result", "clean_win",
        "engine_error", "api_error",
        "task_commands_created", "duplicate_submits",
        "active_tasks_peak", "reallocation_requests",
        "safety_pass", "safety_rejected",
        "tree_create_count", "sim_time", "wall_time",
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
    """/status 资源快照 → (usvs, uavs, tracks)（与 bt_integration_run 同款）"""
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


def _home(uname):
    m = re.search(r"(\d+)$", uname)
    return f"white_usv{m.group(1)}" if m else "white_usv1"


def _pos_of(st, pid, ptype):
    rs = (st or {}).get("资源快照", {}) or {}
    key = "white_usv_states" if ptype == PlatformType.USV else "white_uav_states"
    for u in rs.get("单位状态", {}).get(key, []) or []:
        if u.get("name") == pid and u.get("position"):
            return list(u["position"][:2])
    return [0.0, 300000.0]


def _at_usv(st, pid, ptype):
    rs = (st or {}).get("资源快照", {}) or {}
    key = "white_uav_states" if ptype == PlatformType.UAV else "white_usv_states"
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


class Telemetry:
    def __init__(self):
        self.tcc = 0          # 新任务受理数
        self.dups = 0
        self.realloc = 0
        self.active_peak = 0
        self.tree_create = 0
        self.safety_pass = 0
        self.safety_rejected = 0


def run_episode(scenario, profile, seed):
    wu, wuv, bu = SCEN[scenario]
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)
    logfile = os.path.join(LOG_DIR, f"{scenario}_{profile.replace('_', '')}_s{seed}.log")
    os.makedirs(os.path.dirname(CFG), exist_ok=True)
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
    engine_error = api_error = 0
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
        # ── 分配器（frozen，与 bt_integration_run 相同）──
        alloc = a5.ThreatAllocator()
        usv_map = {u["name"]: None for u in usvs if u.get("is_alive")}
        trk_objs = {}
        for n, t in tracks.items():
            et = a5.EnemyTrack(n, 0.0)
            et.update_obs(t["position"], [-10.0, 0.0], 0.0)
            et.is_ship = t.get("is_ship", False)
            trk_objs[n] = et
        assign = alloc.allocate_usvs(trk_objs, usvs, usv_map, now,
                                     intent=a5.DEFAULT_INTENT, return_margin=False)
        # ── UAV 任务 ──
        uav_assign = {}
        for u in uavs:
            if not u.get("is_alive"):
                continue
            batt = u.get("battery", 100)
            if batt is not None and batt <= 15:
                uav_assign[u["name"]] = (TaskType.RETURN_RECHARGE, None,
                                         {"base": _home(u["name"])})
            else:
                uav_assign[u["name"]] = (TaskType.SITUATION_UPDATE, None,
                                         {"waypoint": [150000.0, 300000.0]})
        # ── TaskCommand 构建；任务变化才 submit ──
        wanted = {}
        for target, plats in assign.items():
            for pl in plats:
                wanted[pl] = (PlatformType.USV, TaskType.INTERCEPT_LOCK, target, None)
        for u in usvs:
            if u.get("is_alive") and u["name"] not in wanted:
                wanted[u["name"]] = (PlatformType.USV, TaskType.HOLD_POSITION, None, None)
        for uname, (tt, tgt, cons) in uav_assign.items():
            wanted[uname] = (PlatformType.UAV, tt, tgt, cons)
        for u in uavs:
            if u.get("is_alive") and u["name"] not in wanted:
                wanted[u["name"]] = (PlatformType.UAV, TaskType.SITUATION_UPDATE,
                                     None, {"waypoint": [150000.0, 300000.0]})
        for pid, (ptype, tt, tgt, cons) in wanted.items():
            task_id = f"{pid}_{tgt}_{tt.value}" if tgt else f"{pid}_{tt.value}"
            if last_task.get(pid) == task_id:
                continue   # unchanged -> tick only (no resubmit)
            ex = execs.get(pid)
            if ex is None:
                ex = BTPlatformExecutive(pid, ptype)
                execs[pid] = ex
                T.tree_create += 1
            cmd = TaskCommand(task_id, pid, ptype, tt, target_id=tgt,
                              constraints=cons or {})
            ack = ex.submit_task(cmd, now_sim=now)
            if ack.code == AckCode.ACCEPTED:
                T.tcc += 1
            elif ack.code == AckCode.DUPLICATE_IGNORED:
                T.dups += 1
            last_task[pid] = task_id
        # ── 死亡平台注销 ──
        alive_names = {u["name"] for u in usvs if u.get("is_alive")} | \
                      {u["name"] for u in uavs if u.get("is_alive")}
        for pid in list(execs):
            if pid not in alive_names:
                ex = execs.pop(pid)
                if ex.active_task:
                    ex.cancel_task(CancelTaskRequest(pid, ex.active_task.task_id))
        # ── tick 全部执行器 → 有限合法动作空间 ──
        requests = []
        for pid, ex in execs.items():
            ptype = ex.platform_type
            pst = {"name": pid, "position": _pos_of(st, pid, ptype),
                   "speed": 20.0, "heading": 90.0, "is_alive": True,
                   "is_at_usv": _at_usv(st, pid, ptype)}
            if ptype == PlatformType.USV:
                pst["is_locking"], pst["locking_unit"] = _locking(st, pid)
            ctxt = ExecutionContext(pid, ptype, now, pst, tracks,
                                    safety_feedback=safety_fb)
            r = ex.tick(ctxt)
            if r.task_feedback and r.task_feedback.need_reallocation:
                T.realloc += 1
            requests.extend(r.action_requests)
        T.active_peak = max(T.active_peak, len(execs))
        # ── 具体动作（数值来自树内计算/任务约束，无预设值）→ 安全过滤 → /apply ──
        adapter = BTActionAdapter()
        payload = adapter.to_apply_payload(requests)
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
            T.safety_pass += sum(1 for i in resp.get("执行结果", [])
                                 if i.get("成功") and not i.get("跳过"))
            T.safety_rejected += sum(1 for i in resp.get("执行结果", [])
                                     if i.get("跳过"))
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
        "engine_error": engine_error, "api_error": api_error,
        "task_commands_created": T.tcc, "duplicate_submits": T.dups,
        "active_tasks_peak": T.active_peak,
        "reallocation_requests": T.realloc,
        "safety_pass": T.safety_pass, "safety_rejected": T.safety_rejected,
        "tree_create_count": T.tree_create, "sim_time": round(last_now, 1),
        "wall_time": round(wall, 1),
        "enemy_kills": int(reward.get("black_killed", 0) or 0),
        "friendly_usv_dead": int(reward.get("white_ship_killed", 0) or 0),
    }
    with open(logfile, "w") as f:
        f.write(json.dumps(row, ensure_ascii=False, indent=1))
    return row


def main():
    ap = argparse.ArgumentParser(description="行为树端口驱动（服务器）")
    ap.add_argument("--scenario", default=None, choices=list(SCEN))
    ap.add_argument("--profile", default=None, choices=PROFILES)
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "integration_results.csv")
    done = set()
    if os.path.exists(path):
        done = {(r["scenario"], r["opponent_profile"], int(r["seed"]))
                for r in csv.DictReader(open(path))}

    runs = []
    if args.scenario and args.profile and args.seed:
        runs = [(args.scenario, args.profile, args.seed)]
    elif args.scenario:
        runs = [(args.scenario, p, s) for p in PROFILES for s in SEEDS]
    else:
        runs = [("S1", "B0_RANDOM", s) for s in SEEDS]

    for scenario, profile, seed in runs:
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
              f"tcc={row['task_commands_created']} wall={row['wall_time']}s", flush=True)
    print("[done]")


if __name__ == "__main__":
    sys.exit(main())
