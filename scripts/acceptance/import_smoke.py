#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Acceptance: import smoke for the minimum stable runtime dependencies.

Read-only. No secrets. No policy behavior.

Usage:
    ${PYTHON:-python} scripts/acceptance/import_smoke.py
"""
import importlib
import sys

MODULES = [
    "fastapi",
    "uvicorn",
    "pydantic",
    "grpc",
    "requests",
    "numpy",
    "pandas",
]


def main():
    failed = []
    for name in MODULES:
        try:
            importlib.import_module(name)
            print("OK   %s" % name)
        except Exception as exc:  # noqa: BLE001
            failed.append(name)
            print("FAIL %s (%s)" % (name, exc))
    print("-" * 40)
    if failed:
        print("IMPORT_SMOKE = FAIL missing=%s" % ",".join(failed))
        return 1
    print("IMPORT_SMOKE = PASS (%d modules)" % len(MODULES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
