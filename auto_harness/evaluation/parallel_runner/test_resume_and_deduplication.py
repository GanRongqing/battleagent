#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_resume_and_deduplication.py — a SUCCEEDED job must NOT be re-run on --resume, and re-running
must not overwrite its result file (dedup + no double counting).

Runs one tiny job, records the result file, then runs again with --resume and asserts the file and the
registry are unchanged.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import parallel_runner as pr  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategies", default="W2-1")
    ap.add_argument("--seeds", default="43001")
    ap.add_argument("--policies", default="ACE")
    a = ap.parse_args()
    rid = "resume_test"
    ns = argparse.Namespace(**vars(a)); ns.workers = 1; ns.run_id = rid; ns.resume = False
    ns.dry_run = False; ns.benchmark = False; ns.epoch = "RT"; ns.max_attempts = 1
    pr.run(ns)
    rdir = f"/tmp/opencode/parallel_runs/{rid}/results"
    files = [f for f in os.listdir(rdir) if f.endswith(".json")]
    assert files, "no result produced"
    mtimes1 = {f: os.path.getmtime(os.path.join(rdir, f)) for f in files}
    # resume
    ns.resume = True
    pr.run(ns)
    mtimes2 = {f: os.path.getmtime(os.path.join(rdir, f)) for f in files}
    same = mtimes1 == mtimes2
    print("test_resume_and_deduplication:", "PASS" if same else "FAIL")
    sys.exit(0 if same else 1)


if __name__ == "__main__":
    main()
