#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""det_capture.py — STAGE A: capture 3 same-seed runs (t=0,30,60) under DETERMINISTIC_STEP_MODE.

Saves the full /status snapshot (white units + radar-captured contacts) per boundary so the
residual non-determinism can be diffed field-by-field / entity-by-entity.

Usage: python det_capture.py <port> <runs> <scenario> <seed> <outdir>
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import urllib.error

PORT = sys.argv[1] if len(sys.argv) > 1 else "8000"
RUNS = int(sys.argv[2]) if len(sys.argv) > 2 else 3
SCEN = sys.argv[3] if len(sys.argv) > 3 else "横向编队-中央汇聚箭头突防"
SEED = int(sys.argv[4]) if len(sys.argv) > 4 else 11001
OUT = sys.argv[5] if len(sys.argv) > 5 else "auto_harness/determinism_residual/traces"
API = f"http://127.0.0.1:{PORT}"
STEPS = [0, 30, 60]


def _get(path):
    try:
        with urllib.request.urlopen(API + path, timeout=20) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"_http": e.code}
    except Exception as e:
        return {"_err": str(e)}


def _post(path):
    try:
        req = urllib.request.Request(API + path, method="POST")
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"_http": e.code}
    except Exception as e:
        return {"_err": str(e)}


def _wait_ready(timeout=25.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        st = _get("/status")
        if isinstance(st, dict) and st.get("已启动") and st.get("等待指令"):
            return st
        time.sleep(0.1)
    return _get("/status")


def _apply(action_type, action_text):
    body = json.dumps({"actions": [{"action_type": action_type, "action_text": action_text}]}).encode()
    req = urllib.request.Request(API + "/apply", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"_err": str(e)}


def run_once(i):
    open("/tmp/opencode/seed_det.txt", "w").write(str(SEED))
    _get("/stop")
    time.sleep(1.5)
    _post("/start?script_name=" + urllib.parse.quote(SCEN))
    d = os.path.join(OUT, f"run{i}")
    os.makedirs(d, exist_ok=True)
    for n, _t in enumerate(STEPS):
        st = _wait_ready()
        with open(os.path.join(d, f"state_t{n*30:03d}.json"), "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False, indent=1)
        if n < len(STEPS) - 1:
            legal = _get("/legal_actions") or {}
            acts = (legal.get("动作", {}) or {}).get("[move]", []) if isinstance(legal, dict) else []
            if not acts:
                print(f"run{i}: no legal move at step {n}")
                break
            txt = acts[0].replace("target_speed=<值>", "target_speed=20").replace("target_course=<值>", "target_course=90")
            _apply("move", txt)
    _get("/stop")


if __name__ == "__main__":
    for i in range(RUNS):
        run_once(i)
        print(f"run {i} captured")
    print("done")
