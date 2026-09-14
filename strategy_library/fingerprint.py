# -*- coding: utf-8 -*-
"""strategy_library/fingerprint.py — empirical behavior fingerprint (fp-v1).

Computes behavior features from TOURNAMENT LOGS ONLY (never from policy cards). Missing
features are recorded as unavailable, never forced to 0. Reuses auto_harness trace parsing
for White-side logs; features are the observable response the opponent induces.
"""
import glob
import hashlib
import os
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "auto_harness", "phase0", "code"))
from auto_harness.phase0.code.trace_derive import parse_episode_log  # noqa: E402
from .policy_models import EmpiricalFingerprint  # noqa: E402

FEATURES = ["first_detection", "first_lock", "first_kill", "resolution_time",
            "lost_track_runs", "capacity_hole_proxy_steps", "reacquire_attempts"]


def logs_hash(paths):
    h = hashlib.sha256()
    for p in sorted(paths):
        h.update(p.encode())
        with open(p, "rb") as f:
            h.update(hashlib.sha256(f.read()).hexdigest().encode())
    return h.hexdigest()


def derive_episode_meta(path):
    """Minimal meta parse reused via trace_derive + outcome row-equivalents."""
    f = parse_episode_log(path)
    return f


def _stats(vals):
    vals = [x for x in vals if x is not None]
    if not vals:
        return None
    return {"mean": round(statistics.mean(vals), 2),
            "median": round(statistics.median(vals), 2),
            "std": round(statistics.pstdev(vals), 2) if len(vals) > 1 else 0.0,
            "n": len(vals)}


def compute_fingerprint(policy_id, log_paths, scenario=None):
    """log_paths: list of per-episode logs (opponent behavior observed by the White log)."""
    log_paths = [p for p in log_paths if os.path.exists(p)]
    meta_all = []
    seeds = []
    for p in log_paths:
        f = derive_episode_meta(p)
        f["resolution_time"] = f.get("resolution") or f.get("sim_end")
        meta_all.append(f)
    behavior = {}
    availability = {}
    for k in FEATURES:
        vals = [f.get(k) for f in meta_all if f.get(k) is not None]
        availability[k] = bool(vals)
        if vals:
            behavior[k] = _stats(vals)
    # response signature: outcome-derived from meta presence
    clean = sum(1 for f in meta_all if f.get("clean_win") == 1)
    brk = sum(1 for f in meta_all if (f.get("breakthrough") or 0) > 0)
    defeats = sum(1 for f in meta_all if f.get("outcome") == "DEFEAT")
    n = len(meta_all)
    response = {"episodes": n,
                "clean_rate": round(clean / n, 3) if n else None,
                "breakthrough_rate": round(brk / n, 3) if n else None,
                "defeat_rate": round(defeats / n, 3) if n else None}
    return EmpiricalFingerprint(
        policy_id=policy_id, fingerprint_version="fp-v1",
        scenario_set=[scenario] if scenario else [],
        episode_count=n, behavior_features=behavior, response_signature=response,
        feature_availability=availability,
        source_logs_hash=logs_hash(log_paths))
