#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""run_combat.py — run one episode (W5 or C1) vs a strategy on a given API port.

Metrics come ONLY from the agent stdout ([META] + [KILL]); no game log needed (safe for parallel).

Usage:
  python run_combat.py --agent w5|c1 --strategy 1..6 --seed N --port 8000 \
                       --seed-file /tmp/opencode/seed_w0.txt --tag W5|C1 --logdir DIR
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = "/root/miniconda3/envs/hsystem_env/bin/python"

STRATEGIES = {
    1: "横向编队-中央汇聚箭头突防", 2: "菱形编队-接近后扇形展开突防",
    3: "菱形编队-两翼包抄中央突进", 4: "菱形编队-南北两翼镜像夹击",
    5: "菱形编队-中央汇聚箭头突防", 6: "菱形编队-MUSV外侧绕行SUSV中央收缩",
}


def http_stop(port):
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/stop", timeout=10).read()
    except Exception:
        pass


def unique(text, tag):
    return len({m.group(1) for m in re.finditer(rf"\[{tag}\]\s+(\S+)", text)})


def parse_meta(text):
    def g(k):
        mm = re.search(rf"\[META\].*?\b{k}=(\S+)", text)
        return mm.group(1) if mm else None
    return {"friendly_usv_losses": g("friendly_usv_losses"),
            "friendly_uav_losses": g("friendly_uav_losses")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", required=True, choices=["w5", "c1", "expand", "lock", "prelock", "reach"])
    ap.add_argument("--strategy", type=int, required=True, choices=range(1, 7))
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--seed-file", required=True)
    ap.add_argument("--tag", default="C1")
    ap.add_argument("--logdir", default=os.path.join(ROOT, "auto_harness", "combat_exchange", "runs"))
    args = ap.parse_args()

    name = STRATEGIES[args.strategy]
    os.makedirs(args.logdir, exist_ok=True)
    logfile = os.path.join(args.logdir, f"s{args.strategy}_{args.tag}_seed{args.seed}.log")

    with open(args.seed_file, "w") as f:
        f.write(str(args.seed))

    # reset any leftover game state before starting a new episode
    http_stop(args.port)
    time.sleep(1.5)

    env = dict(os.environ)
    env["SCENARIO_SCRIPT"] = name
    env["LLM_ENABLED"] = "false"
    env["PYTHONUNBUFFERED"] = "1"

    t0 = time.time()
    with open(logfile, "w", encoding="utf-8") as f:
        p = subprocess.Popen([PY, "run_agent_wrapper.py", str(args.port), args.agent],
                             cwd=ROOT, env=env, stdout=f, stderr=subprocess.STDOUT)
        p.wait()
    wall = time.time() - t0

    text = open(logfile, encoding="utf-8", errors="replace").read()
    meta = parse_meta(text)
    kills = unique(text, "KILL")
    usv_loss = int(meta["friendly_usv_losses"] or 0)
    cer = ("INF" if usv_loss == 0 and kills > 0 else
           ("0" if kills == 0 and usv_loss == 0 else round(kills / usv_loss, 3)))
    res = ("EXCHANGE_WIN" if kills > usv_loss else
           ("EXCHANGE_DRAW" if kills == usv_loss else "EXCHANGE_LOSS"))
    print(json.dumps({"agent": args.tag, "strategy": args.strategy, "seed": args.seed,
                      "black_kills": kills, "white_usv_losses": usv_loss, "CER": cer,
                      "exchange_result": res, "wall": round(wall, 1)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
