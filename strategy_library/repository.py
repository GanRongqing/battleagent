# -*- coding: utf-8 -*-
"""strategy_library/repository.py — SQLite-backed strategy registry (metadata only)."""
import json
import os
import sqlite3
import threading
import time

DEFAULT_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "strategy_library.db")
SCHEMA = """
CREATE TABLE IF NOT EXISTS strategies (
  strategy_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  side TEXT NOT NULL,
  version TEXT,
  strategy_type TEXT DEFAULT 'harness',
  status TEXT DEFAULT 'experimental',
  description TEXT,
  entrypoint TEXT,
  runtime_mode TEXT,
  parent_id TEXT,
  hash TEXT,
  tags TEXT DEFAULT '[]',
  metadata TEXT DEFAULT '{}',
  created_at TEXT,
  updated_at TEXT
);
"""


class StrategyConflict(Exception):
    pass


class StrategyRepository:
    def __init__(self, db_path=None):
        self.db_path = db_path or os.environ.get("STRATEGY_DB_PATH", DEFAULT_DB)
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self._lock = threading.Lock()
        self._init()

    def _conn(self):
        c = sqlite3.connect(self.db_path)
        c.row_factory = sqlite3.Row
        return c

    def _init(self):
        with self._lock, self._conn() as c:
            c.execute(SCHEMA)
            c.commit()

    @staticmethod
    def _row_to_dict(r):
        d = dict(r)
        try:
            d["tags"] = json.loads(d.get("tags") or "[]")
        except Exception:
            d["tags"] = []
        try:
            d["metadata"] = json.loads(d.get("metadata") or "{}")
        except Exception:
            d["metadata"] = {}
        return d

    def exists(self, strategy_id):
        with self._lock, self._conn() as c:
            r = c.execute("SELECT 1 FROM strategies WHERE strategy_id=?",
                          (strategy_id,)).fetchone()
            return r is not None

    def create_strategy(self, info):
        with self._lock, self._conn() as c:
            if c.execute("SELECT 1 FROM strategies WHERE strategy_id=?",
                         (info.strategy_id,)).fetchone():
                raise StrategyConflict(info.strategy_id)
            c.execute(
                "INSERT INTO strategies(strategy_id,name,side,version,strategy_type,status,"
                "description,entrypoint,runtime_mode,parent_id,hash,tags,metadata,created_at,"
                "updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (info.strategy_id, info.name, info.side, info.version, info.strategy_type,
                 info.status, info.description, info.entrypoint, info.runtime_mode,
                 info.parent_id, info.hash, json.dumps(info.tags or []),
                 json.dumps(info.metadata or {}), info.created_at, info.updated_at))
            c.commit()
        return self.get_strategy(info.strategy_id)

    def get_strategy(self, strategy_id):
        with self._lock, self._conn() as c:
            r = c.execute("SELECT * FROM strategies WHERE strategy_id=?", (strategy_id,)).fetchone()
        return self._row_to_dict(r) if r else None

    def list_strategies(self, side=None, status=None, strategy_type=None):
        q = "SELECT * FROM strategies WHERE 1=1"
        args = []
        if side:
            q += " AND side=?"; args.append(side)
        if status:
            q += " AND status=?"; args.append(status)
        if strategy_type:
            q += " AND strategy_type=?"; args.append(strategy_type)
        q += " ORDER BY strategy_id"
        with self._lock, self._conn() as c:
            rows = c.execute(q, args).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def update_strategy(self, strategy_id, patch):
        cur = self.get_strategy(strategy_id)
        if cur is None:
            return None
        allowed = {"name", "version", "strategy_type", "status", "description", "entrypoint",
                   "runtime_mode", "parent_id", "hash", "tags", "metadata"}
        fields, args = [], []
        for k, v in patch.items():
            if k not in allowed or v is None:
                continue
            if k == "tags":
                v = json.dumps(v or [])
            elif k == "metadata":
                v = json.dumps(v or {})
            fields.append(f"{k}=?"); args.append(v)
        fields.append("updated_at=?"); args.append(time.strftime("%Y-%m-%dT%H:%M:%S"))
        with self._lock, self._conn() as c:
            c.execute(f"UPDATE strategies SET {', '.join(fields)} WHERE strategy_id=?",
                      args + [strategy_id])
            c.commit()
        return self.get_strategy(strategy_id)

    def delete_strategy(self, strategy_id):
        with self._lock, self._conn() as c:
            cur = c.execute("DELETE FROM strategies WHERE strategy_id=?", (strategy_id,))
            c.commit()
            return cur.rowcount > 0


_GLOBAL_REPO = None


def get_repository():
    global _GLOBAL_REPO
    if _GLOBAL_REPO is None:
        _GLOBAL_REPO = StrategyRepository()
    return _GLOBAL_REPO
