#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""tests for Strategy Library (repository + HTTP router via TestClient)."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_tmp = tempfile.mkdtemp()
os.environ["STRATEGY_DB_PATH"] = os.path.join(_tmp, "test_strategies.db")

from strategy_library.repository import StrategyRepository, StrategyConflict  # noqa: E402
from strategy_library.models import StrategyInfo, StrategyCreate  # noqa: E402
from strategy_library.router import router  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    if cond:
        PASS.append(name); print(f"  [PASS] {name}")
    else:
        FAIL.append(name); print(f"  [FAIL] {name} {detail}")


def mk(info_dict):
    return StrategyInfo(**info_dict)


def main():
    repo = StrategyRepository()
    now = "2026-01-01T00:00:00"
    base = {"strategy_id": "s1", "name": "Strat One", "side": "white",
            "version": "1", "strategy_type": "harness", "status": "experimental",
            "created_at": now, "updated_at": now}
    # repository tests
    repo.create_strategy(mk(dict(base)))
    check("T1 create", repo.exists("s1"))
    try:
        repo.create_strategy(mk(dict(base)))
        check("T2 duplicate -> conflict", False)
    except StrategyConflict:
        check("T2 duplicate -> conflict", True)
    check("T3 list", len(repo.list_strategies()) >= 1)
    check("T4 get existing", repo.get_strategy("s1")["name"] == "Strat One")
    check("T5 get missing -> None", repo.get_strategy("nope") is None)
    repo.create_strategy(mk(dict(base, strategy_id="s2", side="black", status="frozen")))
    check("T8 filter side=white", all(x["side"] == "white" for x in repo.list_strategies(side="white")))
    check("T9 filter status=frozen",
          all(x["status"] == "frozen" for x in repo.list_strategies(status="frozen")))
    up = repo.update_strategy("s1", {"name": "Strat One Renamed", "tags": ["x"]})
    check("T10 patch update", up and up["name"] == "Strat One Renamed" and "x" in up["tags"])
    check("T6 delete", repo.delete_strategy("s2") is True)
    check("T7 delete missing", repo.delete_strategy("s2") is False)
    # persistence across reopen (same db path)
    repo2 = StrategyRepository()
    check("T11 persistence across reopen", repo2.get_strategy("s1")["name"] == "Strat One Renamed")

    # HTTP API
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    r = client.post("/strategies", json={"strategy_id": "http1", "name": "HTTP One",
                                         "side": "white", "status": "experimental"})
    check("HTTP POST create", r.status_code == 201 and r.json()["strategy_id"] == "http1")
    r = client.post("/strategies", json={"strategy_id": "http1", "name": "dup",
                                         "side": "white"})
    check("HTTP POST duplicate -> 409", r.status_code == 409)
    r = client.get("/strategies?side=white")
    check("HTTP GET list+filter", r.status_code == 200 and r.json())
    r = client.get("/strategies/http1")
    check("HTTP GET detail", r.status_code == 200 and r.json()["name"] == "HTTP One")
    r = client.get("/strategies/missing123")
    check("HTTP GET missing -> 404", r.status_code == 404)
    r = client.patch("/strategies/http1", json={"name": "HTTP One v2", "status": "frozen"})
    check("HTTP PATCH update", r.status_code == 200 and r.json()["name"] == "HTTP One v2")
    r = client.delete("/strategies/http1")
    check("HTTP DELETE", r.status_code == 204)
    r = client.get("/strategies/http1")
    check("HTTP 404 after delete", r.status_code == 404)
    r = client.delete("/strategies/http1")
    check("HTTP DELETE missing -> 404", r.status_code == 404)
    r = client.post("/strategies", json={"strategy_id": "bad", "name": "b", "side": "red"})
    check("HTTP invalid side -> 422", r.status_code == 422)

    print("=" * 60)
    print(f"PASS: {len(PASS)}  FAIL: {len(FAIL)}")
    if FAIL:
        print("FAILED:", FAIL)
    return 0 if not FAIL else 1


if __name__ == "__main__":
    sys.exit(main())
