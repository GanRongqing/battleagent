#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""coevolution_final/determinism_probe.py — run the SAME config twice, compare results.

Definitive check that a (code, seed, composition) run is reproducible. If the two runs
match exactly => the sim + agent are deterministic under the RNG reseed control; any
across-day result differences must then be code-state differences. If they differ =>
residual nondeterminism (unseeded RNG source) and the paired-FINAL must be interpreted
as a noisy descriptive design.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from w6_dev_runner import run_one  # noqa: E402
import json  # noqa: E402

OUT = os.path.dirname(os.path.abspath(__file__))


def read_json(p):
    try:
        return json.load(open(p))
    except Exception:
        return {}


def main():
    profile, seed, ver = "B3_ADAPTIVE", 4001, "W6"
    results = []
    for attempt in (1, 2):
        row = run_one("S1", profile, seed, ver)
        d = read_json("/tmp/opencode/w6_metrics.json")
        key = (row["result"], row["clean_win"], row["enemy_kills"], row["friendly_usv_dead"],
               row["breakthrough"], row["resolution_time"],
               d.get("screen_assignments"), d.get("handoff_count"))
        results.append(key)
        print(f"attempt {attempt}: {key}", flush=True)
    print("MATCH" if results[0] == results[1] else "DIFFER", flush=True)
    with open(os.path.join(OUT, "determinism_probe.txt"), "w") as f:
        f.write("attempt1=%r\nattempt2=%r\nVERDICT=%s\n" %
                (results[0], results[1], "MATCH" if results[0] == results[1] else "DIFFER"))


if __name__ == "__main__":
    sys.exit(main())
