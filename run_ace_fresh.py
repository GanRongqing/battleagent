#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""run_ace_fresh.py — Fresh N5: 6 strategies x 5 seeds (12201-12205) x 2 policies = 60 episodes.

Counterbalanced run order within each (strategy, seed) block:
  odd seed  -> ACE then W5
  even seed -> W5  then ACE
Blocks distributed round-robin across 6 workers (each worker owns port 8000+k*100).
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
COLS = ["agent", "strategy", "seed", "run_order", "black_kills", "white_usv_losses", "CER",
        "exchange_result", "wall"]


def build_blocks():
    blocks = []
    for sid in range(1, 7):
        for seed in (12201, 12202, 12203, 12204, 12205):
            if seed % 2 == 1:
                order = [("expand", "ACE"), ("w5", "W5")]   # ACE -> W5
            else:
                order = [("w5", "W5"), ("expand", "ACE")]   # W5 -> ACE
            blocks.append((sid, seed, order))
    return blocks


def worker(k, blocks):
    port = 8000 + k * 100
    seed_file = f"/tmp/opencode/seed_w{k}.txt"
    out_path = os.path.join(OUT, f"fresh_worker_{k}.jsonl")
    with open(out_path, "w", encoding="utf-8") as f:
        for (sid, seed, order) in blocks:
            for i, (agent, tag) in enumerate(order, 1):
                p = subprocess.run(
                    [PY, "run_combat.py", "--agent", agent, "--strategy", str(sid),
                     "--seed", str(seed), "--port", str(port), "--seed-file", seed_file,
                     "--tag", tag, "--logdir", LOGDIR],
                    cwd=ROOT, capture_output=True, text=True)
                line = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else ""
                try:
                    j = json.loads(line)
                except Exception:
                    j = {}
                j["run_order"] = i
                f.write(json.dumps(j) + "\n")
                f.flush()
                print(f"[w{k}] s{sid} seed{seed} {tag}: {j.get('black_kills')}k/{j.get('white_usv_losses')}l",
                      flush=True)


def main():
    blocks = build_blocks()
    worker_blocks = [[] for _ in range(N_WORKERS)]
    for i, b in enumerate(blocks):
        worker_blocks[i % N_WORKERS].append(b)
    procs = [mp.Process(target=worker, args=(k, worker_blocks[k])) for k in range(N_WORKERS)]
    for p in procs:
        p.start()
    for p in procs:
        p.join()
    rows = []
    for k in range(N_WORKERS):
        p = os.path.join(OUT, f"fresh_worker_{k}.jsonl")
        if os.path.exists(p):
            for line in open(p, encoding="utf-8"):
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except Exception:
                        pass
    csv_path = os.path.join(OUT, "08_FRESH_EPISODES.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for r in sorted(rows, key=lambda r: (r["seed"], r["strategy"], r["run_order"])):
            w.writerow({k: r.get(k, "") for k in COLS})
    print(f"MERGED {len(rows)} fresh episodes -> {csv_path}")


if __name__ == "__main__":
    main()
