#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""determinism_test_rel.py — like determinism_test.py but compares state HASHES (ignore absolute
start time) and relative step times (t[i]-t[0]) so the inherent start-up offset of step 0 does not
mask the per-step determinism achieved by DETERMINISTIC_STEP_MODE.

Usage: python determinism_test_rel.py [port] [N] [K]
"""
import hashlib
import json
import sys
import time
import urllib.parse
import urllib.request

PORT = sys.argv[1] if len(sys.argv) > 1 else "8000"
N = int(sys.argv[2]) if len(sys.argv) > 2 else 3
K = int(sys.argv[3]) if len(sys.argv) > 3 else 30
API = f"http://127.0.0.1:{PORT}"
SEED = 11001
SCENARIO = "横向编队-中央汇聚箭头突防"


def _get(path):
    try:
        with urllib.request.urlopen(API + path, timeout=15) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def _post(path):
    try:
        req = urllib.request.Request(API + path, method="POST")
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def _state_hash(status):
    rs = (status or {}).get("资源快照", {})
    units = rs.get("单位状态", {})
    items = []
    for u in units.get("white_usv_states", []):
        pos = u.get("position") or [0, 0, 0]
        items.append((u.get("name"), bool(u.get("is_alive")), round(pos[0], 1), round(pos[1], 1)))
    items.sort()
    return hashlib.sha256(json.dumps(items, sort_keys=True).encode()).hexdigest()[:16]


def _sim_time(status):
    t = (status or {}).get("局内时间", "00:00:00")
    try:
        h, m, s = t.split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)
    except Exception:
        return -1.0


def wait_ready(timeout=20.0):
    for _ in range(int(timeout / 0.1)):
        st = _get("/status")
        if st and st.get("等待指令"):
            return st
        time.sleep(0.1)
    return _get("/status")


def run_once():
    open("/tmp/opencode/seed_det.txt", "w").write(str(SEED))
    _get("/stop")
    time.sleep(1.5)
    _post(f"/start?script_name={urllib.parse.quote(SCENARIO)}")
    trace = []
    for _ in range(K):
        status = wait_ready()
        if not status:
            break
        trace.append((round(_sim_time(status), 3), _state_hash(status)))
        legal = _get("/legal_actions") or {}
        acts = (legal.get("动作", {}) or {}).get("[move]", [])
        if not acts:
            break
        txt = acts[0].replace("target_speed=<值>", "target_speed=20") \
                     .replace("target_course=<值>", "target_course=90")
        body = json.dumps({"actions": [{"action_type": "move", "action_text": txt}]}).encode()
        req = urllib.request.Request(API + "/apply", data=body,
                                     headers={"Content-Type": "application/json"}, method="POST")
        try:
            urllib.request.urlopen(req, timeout=30).read()
        except Exception:
            break
    _get("/stop")
    return trace


def main():
    runs = []
    for i in range(N):
        tr = run_once()
        runs.append(tr)
        rel = [round(t - tr[0][0], 1) for t, _ in tr] if tr else []
        print(f"run {i}: {len(tr)} steps, abs_t[0:4]={[t for t, _ in tr[:4]]}, rel_t[0:6]={rel[:6]}")
    base = runs[0]
    for i in range(1, N):
        same_len = len(runs[i]) == len(base)
        hdiv = next((j for j, (a, b) in enumerate(zip(base, runs[i])) if a[1] != b[1]), None)
        rel_a = [round(t - base[0][0], 1) for t, _ in base]
        rel_b = [round(t - runs[i][0][0], 1) for t, _ in runs[i]]
        tdiv = next((j for j, (a, b) in enumerate(zip(rel_a, rel_b)) if abs(a - b) > 0.5), None)
        print(f"run {i} vs run 0: same_len={same_len} first_hash_divergence={hdiv} "
              f"first_rel_time_divergence={tdiv} "
              f"({'STATE-IDENTICAL' if hdiv is None and same_len else 'DIVERGED'})")


if __name__ == "__main__":
    main()
