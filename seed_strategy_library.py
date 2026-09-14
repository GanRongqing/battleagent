#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""seed_strategy_library.py — idempotent registration of real project strategies."""
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from strategy_library.repository import StrategyRepository, StrategyConflict  # noqa: E402


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]


def main():
    repo = StrategyRepository()
    now = __import__("time").strftime("%Y-%m-%dT%H:%M:%S")
    w6 = json.load(open(os.path.join(ROOT, "W6_FINAL_MANIFEST.json"))) if os.path.exists(
        os.path.join(ROOT, "W6_FINAL_MANIFEST.json")) else {}
    opp = os.path.join(ROOT, "opponent_profiles.py")
    w5h = sha(os.path.join(ROOT, "agent_hybrid_v5.py"))
    seeds = [
        {"strategy_id": "white-w5", "name": "White Harness W5", "side": "white",
         "version": "W5", "strategy_type": "harness", "status": "frozen",
         "description": "stable deterministic baseline harness",
         "entrypoint": "agent_hybrid_v5.py", "runtime_mode": None,
         "parent_id": None, "hash": w5h, "tags": ["baseline", "deterministic"]},
        {"strategy_id": "white-w6", "name": "White Harness W6", "side": "white",
         "version": "W6-final", "strategy_type": "harness", "status": "completed",
         "description": w6.get("description", "W6 adaptive harness (dev3 deliverable)"),
         "entrypoint": w6.get("agent_entrypoint", "agent_hybrid_w6.py"),
         "runtime_mode": w6.get("runtime_mode", "dev3"),
         "parent_id": "white-w5", "hash": w6.get("agent_hash", "")[:16],
         "tags": ["anti-evasion", "completed"]},
        {"strategy_id": "black-b0", "name": "Black B0 RANDOM", "side": "black",
         "version": "B0", "strategy_type": "opponent", "status": "frozen",
         "description": "random-waypoint baseline opponent",
         "entrypoint": "opponent_profiles.py", "runtime_mode": None, "parent_id": None,
         "hash": sha(opp), "tags": ["opponent", "baseline"]},
        {"strategy_id": "black-b1", "name": "Black B1 MULTI_AXIS", "side": "black",
         "version": "B1", "strategy_type": "opponent", "status": "frozen",
         "description": "multi-axis spatial-group opponent",
         "entrypoint": "opponent_profiles.py", "runtime_mode": None, "parent_id": "black-b0",
         "hash": sha(opp), "tags": ["opponent"]},
        {"strategy_id": "black-b2", "name": "Black B2 COORDINATED_PRESSURE", "side": "black",
         "version": "B2", "strategy_type": "opponent", "status": "frozen",
         "description": "coordinated staggered-lane opponent",
         "entrypoint": "opponent_profiles.py", "runtime_mode": None, "parent_id": "black-b1",
         "hash": sha(opp), "tags": ["opponent"]},
        {"strategy_id": "black-b3", "name": "Black B3 ADAPTIVE", "side": "black",
         "version": "B3", "strategy_type": "opponent", "status": "frozen",
         "description": "legal-observation adaptive-replanning opponent",
         "entrypoint": "opponent_profiles.py", "runtime_mode": None, "parent_id": "black-b2",
         "hash": sha(opp), "tags": ["opponent", "adaptive"]},
        {"strategy_id": "white-w7", "name": "White Harness W7", "side": "white",
         "version": "W7-final", "strategy_type": "harness",
         "status": "completed_no_robust_improvement",
         "description": "W7 performance-push generation record; no robust improvement; "
                        "W5-equivalent baseline retained",
         "entrypoint": "agent_hybrid_v5.py", "runtime_mode": "w5-equivalent",
         "parent_id": "white-w5", "hash": (json.load(open(os.path.join(ROOT, "W7_FINAL_MANIFEST.json")))["agent_hash"][:16] if os.path.exists(os.path.join(ROOT, "W7_FINAL_MANIFEST.json")) else None),
         "tags": ["w7", "completed_no_robust_improvement"]},
    ]
    n = 0
    for s in seeds:
        if repo.exists(s["strategy_id"]):
            continue
        info = dict(s)
        info.setdefault("created_at", now)
        info.setdefault("updated_at", now)
        from strategy_library.models import StrategyInfo
        try:
            repo.create_strategy(StrategyInfo(**info))
            n += 1
        except StrategyConflict:
            pass
    print(f"seeded {n} new strategies; total {len(repo.list_strategies())}")


if __name__ == "__main__":
    sys.exit(main())
