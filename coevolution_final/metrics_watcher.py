#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""metrics_watcher.py — copy /tmp/opencode/w6_metrics.json to timestamped snapshots.

The dev sanity runner deletes the dump at the start of every game and only keeps a few
legacy columns in its CSV. This watcher snapshots the dump whenever it changes, so the
full W6 mechanism counters are preserved per game without touching the runner.
"""
import json
import os
import shutil
import time

SRC = "/tmp/opencode/w6_metrics.json"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "w6_dumps")
os.makedirs(OUT, exist_ok=True)
seen_mtime = None
while True:
    try:
        if os.path.exists(SRC):
            mt = os.path.getmtime(SRC)
            if mt != seen_mtime:
                seen_mtime = mt
                dst = os.path.join(OUT, time.strftime("w6_%Y%m%d_%H%M%S.json"))
                shutil.copy(SRC, dst)
    except Exception:
        pass
    time.sleep(2)
