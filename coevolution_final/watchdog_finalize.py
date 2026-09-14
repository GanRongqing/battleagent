#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""coevolution_final/watchdog_finalize.py — unattended FINAL supervisor.

Responsibilities:
  1. Keep coevolution_final/final_runner.py --main alive until final_episode_results.csv
     has 90 episode rows (header + 90). Restarts the runner if it dies early.
  2. When main is complete: run analyze.py, generate_reports.py, print_terminal.py.
  3. Then run the optional W6xB0 regression (30 episodes) if enabled, and finish.
  Logs to coevolution_final/watchdog.log.
"""
import csv
import os
import subprocess
import sys
import time

PY = "/root/miniconda3/envs/hsystem_env/bin/python"
OUT = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(OUT, "final_episode_results.csv")
OPT = os.path.join(OUT, "optional_w6_b0_regression.csv")
MAIN_TARGET = 91      # header + 90
OPT_TARGET = 31       # header + 30
LOG = os.path.join(OUT, "watchdog.log")


def log(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
    print(msg, flush=True)


def sim_ok():
    import urllib.request
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=6) as r:
            return r.status == 200
    except Exception:
        return False


def heal_sim():
    log("sim down; restarting services")
    subprocess.run(["bash", "/tmp/opencode/start_services.sh"], capture_output=True)
    time.sleep(10)


def rowcount(path):
    try:
        return sum(1 for _ in open(path))
    except Exception:
        return 0


def run(script, args):
    log(f"run {script} {args}")
    p = subprocess.Popen([PY, os.path.join(OUT, script)] + args, cwd=OUT)
    p.wait()
    log(f"done {script} rc={p.returncode}")
    return p.returncode


def main():
    log("watchdog start")
    # phase 1: main 90
    while rowcount(MAIN) < MAIN_TARGET:
        if not sim_ok():
            heal_sim()
            time.sleep(5)
        procs = subprocess.run(["pgrep", "-f", "final_runner.py --main"],
                               capture_output=True, text=True).stdout.split()
        if not procs:
            log("final runner dead; relaunching")
            with open(os.path.join(OUT, "final_main.log"), "a") as lf:
                subprocess.Popen([PY, os.path.join(OUT, "final_runner.py"), "--main"],
                                 cwd=os.path.dirname(OUT), stdout=lf, stderr=subprocess.STDOUT)
        time.sleep(60)
    log("MAIN 90 complete")
    run("analyze.py", [])
    run("generate_reports.py", [])
    # terminal summary to file
    with open(os.path.join(OUT, "reports", "TERMINAL_SUMMARY.txt"), "w") as f:
        subprocess.run([PY, os.path.join(OUT, "print_terminal.py")], stdout=f)
    log("main deliverables generated")
    # phase 2: optional W6 x B0 regression (30)
    if os.getenv("RUN_OPTIONAL_W6B0", "1") == "1":
        while rowcount(OPT) < OPT_TARGET:
            procs = subprocess.run(["pgrep", "-f", "final_runner.py --optional-w6b0"],
                                   capture_output=True, text=True).stdout.split()
            if not procs:
                with open(os.path.join(OUT, "final_optional.log"), "a") as lf:
                    subprocess.Popen([PY, os.path.join(OUT, "final_runner.py"),
                                      "--optional-w6b0"], cwd=os.path.dirname(OUT),
                                     stdout=lf, stderr=subprocess.STDOUT)
            time.sleep(60)
        log("OPTIONAL W6xB0 complete")
        with open(os.path.join(OUT, "DONE"), "w") as f:
            f.write("co-evolution FINAL complete: main90 + optional30\n")
    else:
        with open(os.path.join(OUT, "DONE"), "w") as f:
            f.write("co-evolution FINAL main90 complete (optional skipped)\n")
    log("ALL DONE")


if __name__ == "__main__":
    sys.exit(main())
