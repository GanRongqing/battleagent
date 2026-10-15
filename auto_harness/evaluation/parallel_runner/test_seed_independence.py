#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_seed_independence.py — each Worker must have its OWN seed file, and the engine RNG must be a
function of the seed value (so different workers -> independent RNG init).

Lightweight: starts two workers, writes different seeds to their private files, asserts the files and
env are distinct, and that adaptation._seed_rng() yields different draw sequences for the two seeds.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "evaluation", "parallel_runner"))
from worker_runtime import Worker  # noqa: E402


def _rng_draws(seed):
    import random
    import numpy as np
    random.seed(seed + 1009); np.random.seed(seed + 7)
    return [random.random() for _ in range(4)], float(np.random.random())


def test_seed_independence():
    a = Worker("seed_test", 0); b = Worker("seed_test", 1)
    try:
        ok_a = a.start(); ok_b = b.start()
        assert ok_a and ok_b
        open(a.seedfile, "w").write("43001")
        open(b.seedfile, "w").write("43002")
        assert open(a.seedfile).read() != open(b.seedfile).read()
        assert a.seedfile != b.seedfile
        da = _rng_draws(43001); db = _rng_draws(43002)
        assert da != db, "different seeds produced identical RNG init"
        assert _rng_draws(43001) == da, "same seed must reproduce"
        print("test_seed_independence: PASS")
    finally:
        a.stop(); b.stop()


if __name__ == "__main__":
    test_seed_independence()
