#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""job_registry.py — persistent Job Registry for the parallel evaluation runner.

Job identity = (Experiment, Epoch, Strategy, Policy, Seed, EngineHash, ScenarioHash). Each job has a
status; only fully-validated episodes are SUCCEEDED. Supports resume (skip SUCCEEDED) and retry of
INVALID/FAILED jobs. Writes are atomic (single scheduler writer; per-job files too).
"""
import json
import os
import tempfile

PENDING, RUNNING, SUCCEEDED, INVALID, RETRYING, FAILED = \
    "PENDING", "RUNNING", "SUCCEEDED", "INVALID", "RETRYING", "FAILED"


def job_key(j):
    return f"{j['Experiment']}|{j['Epoch']}|{j['Strategy']}|{j['Policy']}|{j['Seed']}|{j['EngineHash']}|{j['ScenarioHash']}"


class JobRegistry:
    def __init__(self, path):
        self.path = path
        self.jobs = {}   # key -> job dict
        if os.path.exists(path):
            for j in json.load(open(path)):
                self.jobs[job_key(j)] = j

    def add(self, j):
        j = dict(j)
        j.setdefault("Status", PENDING)
        j.setdefault("Attempts", 0)
        j.setdefault("Result", None)
        k = job_key(j)
        if k not in self.jobs:
            self.jobs[k] = j
        return self.jobs[k]

    def set(self, j, status, result=None):
        j["Status"] = status
        if result is not None:
            j["Result"] = result
        self._flush()

    def bump(self, j):
        j["Attempts"] = int(j.get("Attempts", 0)) + 1
        self._flush()

    def _flush(self):
        d = os.path.dirname(os.path.abspath(self.path)); os.makedirs(d, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=d)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(list(self.jobs.values()), f, ensure_ascii=False, indent=1)
        os.replace(tmp, self.path)

    def all(self):
        return list(self.jobs.values())

    def runnable(self, max_attempts=2):
        out = []
        for j in self.jobs.values():
            if j["Status"] in (PENDING, RETRYING):
                out.append(j)
            elif j["Status"] in (INVALID, FAILED) and j.get("Attempts", 0) < max_attempts:
                j["Status"] = RETRYING
                out.append(j)
        self._flush()
        return out

    def succeeded(self):
        return [j for j in self.jobs.values() if j["Status"] == SUCCEEDED]

    def stats(self):
        from collections import Counter
        return dict(Counter(j["Status"] for j in self.jobs.values()))
