# -*- coding: utf-8 -*-
"""provenance.py — E15 episode identity helpers (pure, testable)."""
import hashlib
import os


def make_episode_id(run_id, scenario, policy, seed, attempt):
    return f"{run_id}:{scenario}:{policy}:{seed}:a{int(attempt)}"


def _short(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:10]


def agent_log_name(scenario, policy, seed, attempt, episode_id):
    safe = scenario.replace("/", "_").replace(" ", "_")
    return f"ep_{safe}_{policy}_{seed}_a{int(attempt)}_{_short(episode_id)}.log"


def manifest_record(run_id, episode_id, attempt, worker_id, scenario_id, scenario_name,
                    route_digest, policy_id, seed, actual_seed, engine_hash, pid, api_port, start, end):
    return {"run_id": run_id, "episode_id": episode_id, "attempt_id": int(attempt),
            "worker_id": worker_id, "scenario_id": scenario_id, "scenario_name": scenario_name,
            "route_digest": route_digest, "policy_id": policy_id, "seed": seed,
            "actual_engine_seed": actual_seed, "engine_hash": engine_hash, "pid": pid,
            "api_port": api_port, "start_time": start, "end_time": end}


def file_sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def dedupe_by_content(paths):
    """Return (unique_paths, duplicate_paths) keyed by content SHA-256 (duplicate game logs)."""
    seen, uniq, dup = {}, [], []
    for p in paths:
        h = file_sha(p)
        if h in seen:
            dup.append(p)
        else:
            seen[h] = p
            uniq.append(p)
    return uniq, dup
