#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""parallel_runner.py — CPU-aware multi-process evaluation runner (Episode-level parallelism).

Each Worker process owns a fully isolated base_server + sim_server + FastAPI + agent (private ports,
private seed file, private api_logs, private cwd), so episodes never share mutable runtime state.
Bounded worker pool + dynamic scheduling (a free worker immediately takes the next job). Persistent
registry supports --resume. No tactical/physics changes; result CSV schema is backward compatible.

Usage:
  python parallel_runner.py --strategies W2-1,W2-6,W2-2,W2-4 --seeds 43001..43005 --policies ACE,C7
  python parallel_runner.py --workers 4 --resume --epoch E2
  python parallel_runner.py --benchmark --workers 1,2,4
  python parallel_runner.py --dry-run
"""
import argparse
import hashlib
import json
import multiprocessing as mp
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from resource_detector import detect, plan                     # noqa: E402
from job_registry import JobRegistry, PENDING, RUNNING, SUCCEEDED, INVALID, FAILED, RETRYING, job_key  # noqa: E402
import result_aggregator as agg                                # noqa: E402

PROJ = "/root/autodl-tmp/hsystem"
OUTROOT = os.path.join(PROJ, "auto_harness", "evaluation", "parallel_runner")
STRATS = {"W2-1": "横向编队-中央汇聚箭头突防", "W2-2": "菱形编队-接近后扇形展开突防",
          "W2-3": "菱形编队-两翼包抄中央突进", "W2-4": "菱形编队-南北两翼镜像夹击",
          "W2-5": "菱形编队-中央汇聚箭头突防", "W2-6": "菱形编队-MUSV外侧绕行SUSV中央收缩"}
POLICY = {"ACE": "expand", "C7": "sync", "C9": "demand", "C10": "budget", "C11": "spare", "C12": "bearing", "C13": "safeuav", "C14": "coverage", "C15": "passive", "LIFEDBG": "lifedbg"}
ACE_SHA = "7527253c6d5a4bba198e478a990443354ecf5d8cf4e1c98ace66ce50dc809497"

_WORKER = None
_RESULTS_DIR = None


def _sha(path):
    try:
        return hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]
    except Exception:
        return "NA"


def _init(worker_counter, results_dir, run_id):
    global _WORKER, _RESULTS_DIR
    import atexit
    import signal
    from worker_runtime import Worker
    with worker_counter.get_lock():
        wid = worker_counter.value; worker_counter.value += 1
    w = Worker(run_id, wid)
    if not w.start():
        w.stop(); raise RuntimeError(f"worker {wid} failed to start")
    _WORKER = w
    _RESULTS_DIR = results_dir
    os.makedirs(results_dir, exist_ok=True)

    def _cleanup(*_a):
        try:
            w.stop()
        finally:
            os._exit(0)

    atexit.register(w.stop)
    signal.signal(signal.SIGTERM, _cleanup)
    signal.signal(signal.SIGINT, _cleanup)


def _run_job(job):
    scen = STRATS[job["Strategy"]]; agent = POLICY[job["Policy"]]
    r = _WORKER.run_episode(scen, job["Seed"], agent)
    for _ in range(2):                       # in-run retries (transient /start timeout under load)
        if r["Valid"]:
            break
        time.sleep(8)
        r = _WORKER.run_episode(scen, job["Seed"], agent)
    row = {"Strategy": job["Strategy"], "Policy": job["Policy"], "Seed": job["Seed"],
           "Actual_Engine_Seed": r["Actual_Engine_Seed"], "Valid": r["Valid"],
           "Black_Killed": r["Black_Killed"], "White_USV_Lost": r["White_USV_Lost"],
           "White_UAV_Lost": r["White_UAV_Lost"], "Exchange_Ratio": r["Exchange_Ratio"],
           "Exchange_Result": r["Exchange_Result"], "Terminal_Result": r["Terminal_Result"],
           "Sim_Time": "", "Wall_Time": r["Wall_Time"], "Game_Log": os.path.basename(r["Game_Log"]) if r["Game_Log"] else "",
           "Attempt": job.get("Attempts", 0)}
    with open(os.path.join(_RESULTS_DIR, job_key(job).replace("|", "__") + ".json"), "w", encoding="utf-8") as f:
        json.dump({**job, "Result": row}, f, ensure_ascii=False)
    return row


def build_jobs(strategies, seeds, policies, epoch):
    jobs = []
    for sid in strategies:
        for seed in seeds:
            for pol in policies:
                jobs.append({"Experiment": "e2_ace_c7", "Epoch": epoch, "Strategy": sid, "Policy": pol,
                             "Seed": seed, "EngineHash": _sha(os.path.join(PROJ, "hsystem/simulation/core/base_engine.pyx")),
                             "ScenarioHash": _sha(os.path.join(PROJ, "hsystem/simserver/config/sces.json"))})
    return jobs


def _seed_range(s):
    if ".." in s:
        a, b = s.split(".."); return list(range(int(a), int(b) + 1))
    return [int(x) for x in s.split(",") if x.strip()]


def _reap(run_id, n_workers, base_port=6010, api_port=8010):
    """Kill any surviving worker subprocesses (base_server/sim_server/api) for this run, by cmdline/env."""
    markers = []
    for i in range(max(1, n_workers)):
        bs = base_port + 10 * i
        markers.append((f"--port {bs}", None))
        markers.append((f"--port {bs + 1}", None))
        markers.append((None, f"APP_PORT={api_port + 10 * i}"))
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            cmd = open(f"/proc/{pid}/cmdline", "rb").read().decode("utf-8", "replace").replace("\x00", " ")
        except Exception:
            cmd = ""
        hit = any(m and m in cmd for m, _ in markers)
        if not hit and any(e for _, e in markers):
            try:
                env = open(f"/proc/{pid}/environ", "rb").read().decode("utf-8", "replace")
                hit = any(e and e in env and f"parallel_runs/{run_id}" in env for _, e in markers) \
                      or any(e and e in env for _, e in markers)
            except Exception:
                pass
        if hit:
            try:
                os.kill(int(pid), 9)
            except Exception:
                pass


def run(args):
    det = detect()
    res_plan = plan(det["effective_cpu_cores"], det["effective_memory_limit"])
    run_id = args.run_id or f"run_{int(time.time())}"
    rundir = os.path.join("/tmp/opencode/parallel_runs", run_id)
    results_dir = os.path.join(rundir, "results")
    os.makedirs(results_dir, exist_ok=True)
    jobs = build_jobs(args.strategies.split(","), _seed_range(args.seeds), args.policies.split(","), args.epoch)
    if args.dry_run:
        print(json.dumps({"detected": det, "max_safe_workers": res_plan, "selected_workers": args.workers,
                          "n_jobs": len(jobs), "run_id": run_id}, indent=2))
        return
    reg = JobRegistry(os.path.join(rundir, "registry.json"))
    for j in jobs:
        reg.add(j)
    # a crashed prior run can leave jobs RUNNING; treat them as PENDING for resume
    for j in reg.all():
        if j["Status"] == RUNNING:
            j["Status"] = PENDING
    reg._flush()
    runnable = reg.runnable(max_attempts=args.max_attempts)
    # resume: skip jobs already having a valid result file
    todo = []
    for j in runnable:
        rf = os.path.join(results_dir, job_key(j).replace("|", "__") + ".json")
        if args.resume and os.path.exists(rf):
            try:
                if json.load(open(rf)).get("Result", {}).get("Valid"):
                    reg.set(j, SUCCEEDED); continue
            except Exception:
                pass
        todo.append(j)
    workers = args.workers
    if workers == "auto" or workers == 0:
        workers = res_plan
    workers = max(1, min(int(workers), res_plan, max(1, len(todo)))) if todo else 1
    print(f"[plan] effective_cpu={det['effective_cpu_cores']} max_safe={res_plan} selected={workers} jobs={len(jobs)} todo={len(todo)}", flush=True)
    if not todo:
        _finish(reg, results_dir, args); return
    t0 = time.time()
    for j in todo:
        reg.set(j, RUNNING)
    counter = mp.Value("i", 0)
    try:
        with mp.Pool(processes=workers, initializer=_init, initargs=(counter, results_dir, run_id)) as pool:
            for row in pool.imap_unordered(_run_job, todo, chunksize=1):
                for j in reg.all():
                    if j["Strategy"] == row["Strategy"] and j["Policy"] == row["Policy"] and j["Seed"] == row["Seed"]:
                        reg.bump(j)
                        reg.set(j, SUCCEEDED if row["Valid"] else INVALID, result=row)
                        break
                print(f"[done] {row['Strategy']} {row['Policy']} {row['Seed']} valid={row['Valid']} "
                      f"kills={row['Black_Killed']} loss={row['White_USV_Lost']}", flush=True)
    finally:
        _reap(run_id, workers)
    wall = round(time.time() - t0, 1)
    print(f"[run] wall={wall}s stats={reg.stats()}", flush=True)
    _finish(reg, results_dir, args)


def _finish(reg, results_dir, args):
    rows = agg.load_results(results_dir)
    agg.write_episodes(rows, os.path.join(OUTROOT, "parallel_episodes.csv"))
    mr = agg.main_results(rows)
    agg.write_csv(mr, os.path.join(OUTROOT, "parallel_main_results.csv"),
                  ["Strategy", "Policy", "N", "Black_Killed", "White_USV_Lost", "Exchange_Ratio", "Exchange_Wins"])
    print("[aggregate] valid=", sum(1 for r in rows if str(r.get("Valid")) in ("True", "true", True)),
          "total=", len(rows))


def benchmark(args):
    """Controlled throughput benchmark: same workload at several worker counts."""
    det = detect(); res_plan = plan(det["effective_cpu_cores"], det["effective_memory_limit"])
    counts = [1, 2, 4] if args.workers == "auto" else [int(x) for x in str(args.workers).split(",")]
    wl_strats = args.strategies.split(",")[:1]
    wl_seeds = _seed_range(args.seeds)[:2]
    wl_pol = ["ACE"]
    rows = []
    for w in counts:
        rid = f"bench_w{w}_{int(time.time())}"
        ns = argparse.Namespace(**vars(args))
        ns.workers = w; ns.run_id = rid; ns.resume = False; ns.dry_run = False; ns.epoch = "BENCH"
        ns.strategies = ",".join(wl_strats); ns.seeds = ",".join(str(s) for s in wl_seeds)
        ns.policies = ",".join(wl_pol)
        t0 = time.time(); run(ns); wall = time.time() - t0
        n = len(wl_strats) * len(wl_seeds) * len(wl_pol)
        rows.append({"Workers": w, "Episodes": n, "Wall_s": round(wall, 1),
                     "Episodes_per_hour": round(n / wall * 3600, 2) if wall else "", "EffectiveCPU": det["effective_cpu_cores"]})
        print("[bench]", rows[-1], flush=True)
    agg.write_csv(rows, os.path.join(OUTROOT, "04_THROUGHPUT_BENCHMARK.csv"),
                  ["Workers", "Episodes", "Wall_s", "Episodes_per_hour", "EffectiveCPU"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategies", default="W2-1,W2-6,W2-2,W2-4")
    ap.add_argument("--seeds", default="43001..43005")
    ap.add_argument("--policies", default="ACE,C7")
    ap.add_argument("--workers", default="auto")
    ap.add_argument("--epoch", default="E2")
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--benchmark", action="store_true")
    ap.add_argument("--max-attempts", type=int, default=2)
    a = ap.parse_args()
    if a.workers != "auto":
        a.workers = int(a.workers)
    if a.benchmark:
        benchmark(a)
    else:
        run(a)


if __name__ == "__main__":
    main()
