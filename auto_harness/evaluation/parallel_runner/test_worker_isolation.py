#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_worker_isolation.py — two Workers must have disjoint ports, seed files, api_logs, cwd.

Lightweight: starts both isolated runtimes, asserts disjoint resources + that each base_server/api is
reachable on its own port, then tears down. No episodes are run.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "evaluation", "parallel_runner"))
from worker_runtime import Worker, _http  # noqa: E402


def test_isolation():
    a = Worker("iso_test", 0)
    b = Worker("iso_test", 1)
    assert a.bs_port != b.bs_port and a.api_port != b.api_port
    assert a.seedfile != b.seedfile and a.apilog != b.apilog and a.simdir != b.simdir
    try:
        ok_a = a.start(); ok_b = b.start()
        assert ok_a and ok_b, (ok_a, ok_b)
        assert _http(f"http://127.0.0.1:{a.api_port}/health")
        assert _http(f"http://127.0.0.1:{b.api_port}/health")
        # distinct env in the launched procs
        for w in (a, b):
            env = open(f"/proc/{w.bs.pid}/environ", "rb").read().decode("utf-8", "replace")
            assert f"RW_SEED_FILE={w.seedfile}" in env, "seed file not isolated"
            assert w.simdir in env, "cwd/PYTHONPATH not isolated"
        print("test_worker_isolation: PASS")
    finally:
        a.stop(); b.stop()


if __name__ == "__main__":
    test_isolation()
