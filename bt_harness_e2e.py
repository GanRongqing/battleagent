#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""bt_harness_e2e.py — one real E2E scenario: Harness Allocator → TaskCommand →
submit_task ACCEPTED → >=3 ticks → ActionRequest → POST /apply → feedback → next tick.

Uses the real simulator (frozen White runtime, B0 opponent). The Harness allocator
(agent_hybrid_v5.ThreatAllocator, read-only) produces the assignment; the BT wrapper
(BTPlatformExecutive) owns HOW; BTActionAdapter converts intent → /apply payload.

Writes: BT_HARNESS_INTERFACE_TRACE.md
"""
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
API = "http://127.0.0.1:8000"
CFG = "/tmp/opencode/rw_cfg.txt"

import bt_harness_interface as bhi          # noqa: E402
import agent_hybrid_v5 as a5                # noqa: E402


def http(path, method="GET", data=None):
    import urllib.request
    headers = {}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(API + path, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def get_status():
    try:
        return http("/status")
    except Exception:
        return None


def build_tracks(st):
    """Legal belief from /status whitelist (White radar capture)."""
    rs = (st or {}).get("资源快照", {}) or {}
    intel = (rs.get("观察信息", {}) or {}).get("white_observation", {}) or {}
    tracks = {}
    for e in intel.get("雷达捕获", []) or []:
        if e.get("position"):
            tracks[e["name"]] = {"position": list(e["position"][:2]),
                                 "visible": True, "confidence": 1.0}
    return tracks


def platform_state(st, pid):
    rs = (st or {}).get("资源快照", {}) or {}
    for u in rs.get("单位状态", {}).get("white_usv_states", []) or []:
        if u.get("name") == pid:
            return {"name": pid, "position": list(u.get("position", [0, 0])[:2]),
                    "speed": u.get("speed", 20.0), "heading": u.get("course", 90.0),
                    "is_alive": u.get("is_alive", True)}
    return {"name": pid, "position": [0.0, 300000.0], "speed": 20.0,
            "heading": 90.0, "is_alive": True}


def allocator_command(st):
    """Run the real Harness allocator on the legal observation → a TaskCommand."""
    rs = (st or {}).get("资源快照", {}) or {}
    usvs = rs.get("单位状态", {}).get("white_usv_states", []) or []
    tracks = build_tracks(st)
    # minimal enemy tracks as EnemyTrack beliefs (legal)
    trk_objs = {}
    for name, t in tracks.items():
        et = a5.EnemyTrack(name, 0.0)
        et.update_obs(t["position"], [-10.0, 0.0], 0.0)
        et.is_ship = ("usv" in name.lower())
        trk_objs[name] = et
    alloc = a5.ThreatAllocator()
    usv_map = {u["name"]: None for u in usvs if u.get("is_alive")}
    res = alloc.allocate_usvs(trk_objs, usvs, usv_map, 0.0, intent=a5.DEFAULT_INTENT,
                              return_margin=False)
    for target, plats in res.items():
        if plats:
            return target, plats[0]
    # fallback: first alive usv, first visible enemy
    if usvs and tracks:
        return sorted(tracks)[0], usvs[0]["name"]
    return None, None


def main():
    # start a real scenario (5+5 vs 10, B0)
    with open(CFG, "w") as f:
        f.write("1001 5 5 10 0 fixed_frontage 1.0 B0_RANDOM")
    try:
        http("/stop", "GET")
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
    if not st:
        print("E2E failed: could not start scenario"); return 1

    # wait until White detects at least one enemy (fresh game start)
    target = platform = None
    for _ in range(60):
        st = get_status()
        if st and build_tracks(st):
            target, platform = allocator_command(st)
            if target and platform:
                break
        time.sleep(3)
    if not target or not platform:
        print("E2E failed: no enemy contact within timeout"); return 1

    cmd = bhi.TaskCommand(f"{platform}_{target}_intercept", platform, bhi.PlatformType.USV,
                          bhi.TaskType.INTERCEPT_LOCK, target_id=target)
    ex = bhi.BTPlatformExecutive(platform, bhi.PlatformType.USV)
    ack = ex.submit_task(cmd)
    ad = bhi.BTActionAdapter()

    lines = []
    lines.append("# BT ↔ Harness Interface — E2E Trace\n")
    lines.append(f"- scenario: 5+5 vs 10 combat USV, B0_RANDOM\n- platform: `{platform}`"
                 f"\n- task_id: `{cmd.task_id}`\n- target_id: `{target}`"
                 f"\n- submit ack: **{ack.code.value}**\n")

    safety = None
    sim_now = 0.0
    for tick in range(1, 4):
        st = get_status()
        tracks = build_tracks(st)
        pst = platform_state(st, platform)
        used_safety = dict(safety) if safety else None
        ctxt = bhi.ExecutionContext(platform, bhi.PlatformType.USV, sim_now, pst, tracks,
                                    safety_feedback=used_safety)
        r = ex.tick(ctxt)
        payload = ad.to_apply_payload(r.action_requests)
        try:
            resp = http("/apply", "POST", json.dumps(payload).encode())
        except Exception as e:
            resp = {"error": str(e)}
        # build safety feedback for the next tick
        safety = {}
        if isinstance(resp, dict):
            for item in resp.get("执行结果", []):
                skipped = item.get("跳过") is True
                ok = bool(item.get("成功")) and not skipped
                safety[item.get("动作", "")] = "ACCEPTED" if ok else "REJECTED"
            stats = resp.get("执行统计", "?")
        else:
            safety = {a["action_text"]: "REJECTED" for a in payload["actions"]}
            stats = "error"

        fb = r.task_feedback
        lines.append(f"## tick {tick}\n")
        lines.append(f"- tick_id={r.tick_id}  root_status={r.root_status}  "
                     f"branch={r.active_branch}\n")
        lines.append(f"- context.safety_feedback (used this tick): "
                     f"{json.dumps(used_safety, ensure_ascii=False) if used_safety else '(none)'}\n")
        lines.append("- action_requests:")
        for ar in r.action_requests:
            lines.append(f"  - {ar.platform_id} {ar.action_kind.value} target={ar.target_id} "
                         f"course={ar.course}")
        lines.append("- /apply payload:")
        for a in payload["actions"]:
            lines.append(f"  - [{a['action_type']}] {a['action_text']}")
        lines.append(f"- /apply result: `{stats}`")
        lines.append(f"- task_feedback: phase={fb.phase.value} target={fb.target_id} "
                     f"visible={fb.target_visible} need_reallocation={fb.need_reallocation} "
                     f"reason={fb.reason_code.value}\n")
        # advance sim time in the trace
        try:
            hh, mm, ss = [int(x) for x in str((st or {}).get("局内时间", "00:00:10")).split(":")]
            sim_now = hh * 3600 + mm * 60 + ss
        except Exception:
            sim_now += 1.0

    with open(os.path.join(ROOT, "REAL_BT_HARNESS_TRACE.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("=== E2E done (real trees) ===")
    print(f"platform={platform} target={target} ack={ack.code.value}")
    print("trace written: REAL_BT_HARNESS_TRACE.md")
    print("\n".join(lines))
    try:
        http("/stop", "GET")
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
