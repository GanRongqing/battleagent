#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Acceptance: read-only hash collector for frozen artifacts.

Usage:
    ${PYTHON:-python} scripts/acceptance/collect_hashes.py
"""
import hashlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FILES = [
    "agent_hybrid_v5.py",
    "skills/maritime_commander/SKILL.md",
    "hsystem/pomdp_api/main.py",
    "hsystem/sim_script/20250819TZB/scenario_builder.py",
    "hsystem/sim_script/20250819TZB/scenario_composition.py",
    "bt_harness_interface.py",
    "bt_real_trees.py",
]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    rc = 0
    for rel in FILES:
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            print("MISSING %s" % rel)
            rc = 1
            continue
        print("%s  %s" % (sha256(path), rel))
    return rc


if __name__ == "__main__":
    sys.exit(main())
