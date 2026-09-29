#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""run_ace_dev.py — paired DEV: W5 vs white-combat-0002-v1 (expand), N=2 (12101/12102), 6 strategies.

24 episodes, parallel across 6 workers. Resumable via worker jsonl + final merge.
"""
import csv
import json
import multiprocessing as mp
import os
import subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "auto_harness", "combat_exchange", "allocator_commitment_expansion")
LOGDIR = os.path.join(ROOT, "auto_harness", "combat_exchange", "runs")
PY = "/root/miniconda3/envs/hsystem_env/bin/python"
N_WORKERS = 6
COLS = ["agent", "strategy", "seed", "black_kills", "white_usv_losses", "CER", "exchange_result", "wall"]


def build_episodes():
    eps = []
    for seed in (12101, 12102):
        for sid in range(1, 7):
            for agent, tag in (("w5", "W5"), ("expand", "ACE")):
                eps.append((seed, sid, agent, tag))
    return eps


def worker(k, eps):
    port = 8000 + k * 100
    seed_file = f"/tmp/opencode/seed_w{k}.txt"
    out_path = os.path.join(OUT, f"worker_{k}.jsonl")
    with open(out_path, "w", encoding="utf-8") as f:
        for (seed, sid, agent, tag) in eps:
            p = subprocess.run(
                [PY, "run_combat.py", "--agent", agent, "--strategy", str(sid),
                 "--seed", str(seed), "--port", str(port), "--seed-file", seed_file,
                 "--tag", tag, "--logdir", LOGDIR],
                cwd=ROOT, capture_output=True, text=True)
            line = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else ""
            f.write(line + "\n")
            f.flush()
            print(f"[w{k}] {line}", flush=True)


def main():
    eps = build_episodes()
    worker_eps = [[] for _ in range(N_WORKERS)]
    for i, e in enumerate(eps):
        worker_eps[i % N_WORKERS].append(e)
    procs = [mp.Process(target=worker, args=(k, worker_eps[k])) for k in range(N_WORKERS)]
    for p in procs:
        p.start()
    for p in procs:
        p.join()
    rows = []
    for k in range(N_WORKERS):
        p = os.path.join(OUT, f"worker_{k}.jsonl")
        if os.path.exists(p):
            for line in open(p, encoding="utf-8"):
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except Exception:
                        pass
    csv_path = os.path.join(OUT, "04_DEV_EPISODES.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for r in sorted(rows, key=lambda r: (r["seed"], r["strategy"], r["agent"])):
            w.writerow({k: r.get(k, "") for k in COLS})
    print(f"MERGED {len(rows)} episodes -> {csv_path}")


if __name__ == "__main__":
    main()
