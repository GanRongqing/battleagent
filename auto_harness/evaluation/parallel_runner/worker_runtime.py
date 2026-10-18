#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""worker_runtime.py — one isolated evaluation Worker = its own base_server + sim_server + FastAPI +
agent, with a private working dir, private seed file, private api_logs, and private ports.

Isolation guarantees:
  * RW_SEED_FILE  -> worker_private_dir/seed.txt          (no shared seed file)
  * sim_server.py writes temp.py   -> worker simserver symlink-farm (private cwd)
  * base_server.py writes temp1.py -> worker simserver symlink-farm (private cwd)
  * FastAPI game/runtime logs      -> API_LOG_DIR=worker_private_dir/api_logs (via main.py override)
  * ports                          -> base=6010+10*w, api=8010+10*w (conflict-checked)
Read-only code is shared via symlinks; no mutable runtime data is shared.
"""
import json
import os
import re
import shutil
import socket
import subprocess
import time
import urllib.request

PY = "/root/miniconda3/envs/hsystem_env/bin/python"
HW = "/root/autodl-tmp/hsystem/hsystem"          # engine + simserver + pomdp_api root
PROJ = "/root/autodl-tmp/hsystem"                # repo root (run_agent_wrapper.py lives here)
GAME_LOG_SUBDIR = os.path.join("api_logs", "games")


def _port_free(p):
    """True if nothing is LISTENING on 127.0.0.1:p (connect-based; avoids TIME_WAIT false positives)."""
    s = socket.socket()
    s.settimeout(0.6)
    try:
        s.connect(("127.0.0.1", p))
        return False                      # something is accepting connections
    except (ConnectionRefusedError, socket.timeout, OSError):
        return True
    finally:
        s.close()


def _http(url, timeout=8, post=False):
    req = urllib.request.Request(url, method="POST" if post else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode() or "{}")


class Worker:
    def __init__(self, run_id, worker_id, base_port=6010, api_port=8010, root="/tmp/opencode/parallel_runs"):
        self.wid = worker_id
        self.run_id = run_id
        # Unique ports derived from run_id so sequential invocations can never reconnect to a stale
        # base_server/sim_server left over from a previous episode (E8.1 root cause).
        import hashlib as _h
        _r = int(_h.sha256(str(run_id).encode()).hexdigest()[:6], 16)
        self.bs_port = 16000 + (_r % 400) * 10 + 10 * worker_id
        self.api_port = 26000 + (_r % 400) * 10 + 10 * worker_id
        self.dir = os.path.join(root, run_id, f"w{worker_id}")
        self.simdir = os.path.join(self.dir, "simserver")
        self.seedfile = os.path.join(self.dir, "seed.txt")
        self.apilog = os.path.join(self.dir, "api_logs")
        self.identity_file = os.path.join(self.dir, "runtime_identity.json")
        self.procs = []
        self.ready = False

    # ---- setup ----
    def _symlink_farm(self):
        if os.path.isdir(self.simdir):
            shutil.rmtree(self.simdir, ignore_errors=True)
        os.makedirs(self.simdir, exist_ok=True)
        src = os.path.join(HW, "simserver")
        for name in os.listdir(src):
            if name in (".git", "__pycache__", "temp.py", "temp1.py"):
                continue
            dst = os.path.join(self.simdir, name)
            try:
                os.symlink(os.path.join(src, name), dst)
            except FileExistsError:
                pass

    def start(self):
        self._sweep()   # kill any stale process bound to this run's ports before launching
        os.makedirs(self.dir, exist_ok=True)
        os.makedirs(self.apilog, exist_ok=True)
        self._symlink_farm()
        open(self.seedfile, "w").write("0")
        assert _port_free(self.bs_port), f"base port {self.bs_port} busy"
        assert _port_free(self.api_port), f"api port {self.api_port} busy"
        env = dict(os.environ)
        try:
            if os.path.exists(self.identity_file): os.remove(self.identity_file)
        except Exception: pass
        env.update({"PYTHONPATH": f"{self.simdir}:{HW}:{os.path.join(HW,'simserver')}",
                    "HSYSTEM_ROOT": HW, "RW_SEED_FILE": self.seedfile, "PYTHONHASHSEED": "0",
                    "RUNTIME_IDENTITY_FILE": self.identity_file,
                    "SCENARIO_MODULE_DEBUG": os.path.join(self.dir, "scenario_module.txt")})
        self.bslog = open(os.path.join(self.dir, "base_server.log"), "w")
        self.bs = subprocess.Popen(
            [PY, "-u", os.path.join(self.simdir, "base_server.py"), "--port", str(self.bs_port),
             "--min_simserver_port", str(self.bs_port + 1), "--simserver_num", "1"],
            cwd=self.simdir, env=env, stdout=self.bslog, stderr=subprocess.STDOUT)
        self.procs.append(self.bs)
        # wait for base_server to listen
        for _ in range(120):
            if not _port_free(self.bs_port):
                break
            time.sleep(0.5)
        aenv = dict(env)
        aenv.update({"SIM_HOST": "127.0.0.1", "SIM_PORT": str(self.bs_port), "APP_PORT": str(self.api_port),
                     "DETERMINISTIC_STEP_MODE": "true", "API_LOG_DIR": self.apilog, "LLM_ENABLED": "false"})
        self.apilogf = open(os.path.join(self.dir, "api.log"), "w")
        self.api = subprocess.Popen([PY, "-u", os.path.join(HW, "pomdp_api", "main.py")],
                                    cwd=os.path.join(HW, "pomdp_api"), env=aenv,
                                    stdout=self.apilogf, stderr=subprocess.STDOUT)
        self.procs.append(self.api)
        for _ in range(160):
            try:
                if _http(f"http://127.0.0.1:{self.api_port}/health", timeout=5).get("status") == "ok" \
                        or _http(f"http://127.0.0.1:{self.api_port}/health", timeout=5):
                    self.ready = True
                    break
            except Exception:
                pass
            time.sleep(0.5)
        # settle: give base_server time to register its sim_server before /start is issued
        time.sleep(3.0)
        return self.ready

    # ---- episode ----
    def _meta(self, text):
        def g(k):
            m = re.search(rf"\[META\].*?\b{k}=(\S+)", text); return m.group(1) if m else None
        m = re.search(r"\[META\] result=(\S+)", text)
        return (m.group(1) if m else "UNFINISHED"), g("enemy_kills"), g("friendly_usv_losses"), g("friendly_uav_losses")

    def _newest_game_log(self, scen, t0):
        d = os.path.join(self.apilog, "games")
        best, bt = None, 0
        if not os.path.isdir(d):
            return None
        for f in os.listdir(d):
            p = os.path.join(d, f)
            if f.endswith(".json") and os.path.getmtime(p) >= t0:
                try:
                    if json.load(open(p, encoding="utf-8")).get("script_name") == scen and os.path.getmtime(p) > bt:
                        best, bt = p, os.path.getmtime(p)
                except Exception:
                    pass
        return best

    def run_episode(self, scen, seed, agent, timeout=None):
        open(self.seedfile, "w").write(str(seed))
        actual = open(self.seedfile).read().strip()
        try:
            _http(f"http://127.0.0.1:{self.api_port}/stop", timeout=15)
        except Exception:
            pass
        time.sleep(0.5)
        logf = os.path.join(self.dir, f"ep_{seed}_{agent}.log")
        env = dict(os.environ)
        env.update({"SCENARIO_SCRIPT": scen, "LLM_ENABLED": "false", "PYTHONUNBUFFERED": "1",
                    "RW_SEED_FILE": self.seedfile,
                    "C7_PKG_LOG": os.path.join(self.dir, f"pkg_{seed}_{agent}.json")})
        t0 = time.time()
        with open(logf, "w") as f:
            try:
                subprocess.Popen([PY, "run_agent_wrapper.py", str(self.api_port), agent],
                                 cwd=PROJ, env=env, stdout=f, stderr=subprocess.STDOUT).wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                pass
        wall = round(time.time() - t0, 1)
        text = open(logf, encoding="utf-8", errors="replace").read()
        res, k, l, uav = self._meta(text)
        k = int(k) if k else 0; l = int(l) if l else 0; uav = int(uav) if uav else 0
        gl = self._newest_game_log(scen, t0 - 5)
        valid = ("[META]" in text) and (gl is not None)
        return {"Valid": valid, "Actual_Engine_Seed": actual, "Black_Killed": k, "White_USV_Lost": l,
                "White_UAV_Lost": uav, "Terminal_Result": res, "Wall_Time": wall,
                "Game_Log": gl, "Agent_Log": logf,
                "Exchange_Ratio": ("K:0" if (k == 0 and l == 0) else (round(k / l, 3) if l else "inf")),
                "Exchange_Result": ("EXCHANGE_WIN" if k > l else ("EXCHANGE_TIE" if k == l else "EXCHANGE_LOSS"))}

    def stop(self):
        for p in self.procs:
            try:
                p.terminate()
            except Exception:
                pass
        time.sleep(1)
        for p in self.procs:
            try:
                p.kill()
            except Exception:
                pass
        # base_server forks children that keep the ports; sweep by cmdline/env for THIS worker's ports.
        self._sweep()

    def _sweep(self):
        cmds = [f"--port {self.bs_port}", f"--port {self.bs_port + 1}"]
        envs = [f"APP_PORT={self.api_port}"]
        for pid in os.listdir("/proc"):
            if not pid.isdigit():
                continue
            try:
                cmd = open(f"/proc/{pid}/cmdline", "rb").read().decode("utf-8", "replace").replace("\x00", " ")
            except Exception:
                cmd = ""
            hit = any(c in cmd for c in cmds)
            if not hit:
                try:
                    env = open(f"/proc/{pid}/environ", "rb").read().decode("utf-8", "replace")
                    hit = any(e in env for e in envs)
                except Exception:
                    pass
            if hit:
                try:
                    os.kill(int(pid), 9)
                except Exception:
                    pass
