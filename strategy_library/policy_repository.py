# -*- coding: utf-8 -*-
"""strategy_library/policy_repository.py — SQLite tables for immutable policies (extends
Strategy Library DB). Separation: cards / artifacts / fingerprints / validations."""
import json
import os
import sqlite3
import threading

DEFAULT_DB = os.environ.get("STRATEGY_DB_PATH",
                            os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                         "strategy_library.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS policy_cards (
  policy_id TEXT PRIMARY KEY,
  version TEXT NOT NULL, side TEXT NOT NULL, strategy_family TEXT NOT NULL,
  declared_intent TEXT NOT NULL, trigger_and_switch TEXT NOT NULL,
  known_strengths TEXT NOT NULL, known_weaknesses TEXT NOT NULL,
  declared_traits TEXT NOT NULL, status TEXT NOT NULL, evaluation_role TEXT NOT NULL,
  parent_policy_id TEXT, description TEXT, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS policy_artifacts (
  policy_id TEXT PRIMARY KEY, entrypoint TEXT, artifact_files TEXT,
  artifact_hash TEXT, config_path TEXT, config_hash TEXT, prompt_path TEXT,
  prompt_hash TEXT, template_path TEXT, template_hash TEXT,
  environment_hash TEXT, simulator_hash TEXT, opponent_module_hash TEXT,
  git_commit TEXT, bundle_hash TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS policy_fingerprints (
  fingerprint_id INTEGER PRIMARY KEY AUTOINCREMENT,
  policy_id TEXT, fingerprint_version TEXT, scenario_set TEXT, seed_set TEXT,
  episode_count INTEGER, behavior_features TEXT, response_signature TEXT,
  feature_availability TEXT, source_logs_hash TEXT, computed_at TEXT);
CREATE TABLE IF NOT EXISTS policy_validations (
  validation_id INTEGER PRIMARY KEY AUTOINCREMENT,
  candidate_policy_id TEXT, reference_policy_id TEXT, artifact_same INTEGER,
  semantic_difference TEXT, empirical_distance REAL, feature_differences TEXT,
  multi_seed_stable INTEGER, multi_scenario_stable INTEGER, novelty_verdict TEXT,
  evaluation_role TEXT, evidence TEXT, created_at TEXT);
"""


class PolicyRepository:
    def __init__(self, db_path=None):
        self.db_path = db_path or DEFAULT_DB
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self._lock = threading.Lock()
        self._init()

    def _conn(self):
        c = sqlite3.connect(self.db_path)
        c.row_factory = sqlite3.Row
        return c

    def _init(self):
        with self._lock, self._conn() as c:
            c.executescript(SCHEMA)
            c.commit()

    # ---- cards ----
    def upsert_card(self, card):
        with self._lock, self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO policy_cards(policy_id,version,side,strategy_family,"
                "declared_intent,trigger_and_switch,known_strengths,known_weaknesses,"
                "declared_traits,status,evaluation_role,parent_policy_id,description,"
                "created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (card.policy_id, card.version, card.side, card.strategy_family,
                 json.dumps(card.declared_intent), json.dumps(card.trigger_and_switch),
                 json.dumps(card.known_strengths), json.dumps(card.known_weaknesses),
                 json.dumps(card.declared_traits), card.status, card.evaluation_role,
                 card.parent_policy_id, card.description, card.created_at, card.updated_at))
            c.commit()

    def get_card(self, policy_id):
        with self._lock, self._conn() as c:
            r = c.execute("SELECT * FROM policy_cards WHERE policy_id=?", (policy_id,)).fetchone()
        return self._row_card(r) if r else None

    def list_cards(self, side=None, status=None):
        q = "SELECT * FROM policy_cards WHERE 1=1"
        a = []
        if side:
            q += " AND side=?"; a.append(side)
        if status:
            q += " AND status=?"; a.append(status)
        with self._lock, self._conn() as c:
            return [self._row_card(r) for r in c.execute(q + " ORDER BY policy_id", a).fetchall()]

    @staticmethod
    def _row_card(r):
        d = dict(r)
        for k in ("declared_intent", "trigger_and_switch", "known_strengths",
                  "known_weaknesses", "declared_traits"):
            try:
                d[k] = json.loads(d.get(k) or "{}")
            except Exception:
                pass
        return d

    def update_card_metadata(self, policy_id, patch):
        cur = self.get_card(policy_id)
        if cur is None:
            return None
        allowed = {"description", "evaluation_role", "known_strengths", "known_weaknesses",
                   "declared_traits"}
        fields, vals = [], []
        for k in allowed:
            if k in patch and patch[k] is not None:
                v = patch[k]
                fields.append(f"{k}=?")
                vals.append(json.dumps(v) if isinstance(v, (list, dict)) else v)
        if not fields:
            return cur
        fields.append("updated_at=?")
        vals.append(json.loads if False else __import__("time").strftime("%Y-%m-%dT%H:%M:%S"))
        vals.append(policy_id)
        with self._lock, self._conn() as c:
            c.execute(f"UPDATE policy_cards SET {', '.join(fields)} WHERE policy_id=?",
                      vals)
            c.commit()
        return self.get_card(policy_id)

    # ---- artifacts ----
    def upsert_artifact(self, m):
        with self._lock, self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO policy_artifacts(policy_id,entrypoint,artifact_files,"
                "artifact_hash,config_path,config_hash,prompt_path,prompt_hash,template_path,"
                "template_hash,environment_hash,simulator_hash,opponent_module_hash,git_commit,"
                "bundle_hash,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (m.policy_id, m.entrypoint, json.dumps(m.artifact_files), m.artifact_hash,
                 m.config_path, m.config_hash, m.prompt_path, m.prompt_hash, m.template_path,
                 m.template_hash, m.environment_hash, m.simulator_hash,
                 m.opponent_module_hash, m.git_commit, m.bundle_hash, m.created_at))
            c.commit()

    def get_artifact(self, policy_id):
        with self._lock, self._conn() as c:
            r = c.execute("SELECT * FROM policy_artifacts WHERE policy_id=?",
                          (policy_id,)).fetchone()
        if not r:
            return None
        d = dict(r)
        try:
            d["artifact_files"] = json.loads(d.get("artifact_files") or "[]")
        except Exception:
            d["artifact_files"] = []
        return d

    # ---- fingerprints ----
    def add_fingerprint(self, fp):
        with self._lock, self._conn() as c:
            cur = c.execute(
                "INSERT INTO policy_fingerprints(policy_id,fingerprint_version,scenario_set,"
                "seed_set,episode_count,behavior_features,response_signature,"
                "feature_availability,source_logs_hash,computed_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (fp.policy_id, fp.fingerprint_version, json.dumps(fp.scenario_set),
                 json.dumps(fp.seed_set), fp.episode_count, json.dumps(fp.behavior_features),
                 json.dumps(fp.response_signature), json.dumps(fp.feature_availability),
                 fp.source_logs_hash, fp.computed_at))
            c.commit()
            return cur.lastrowid

    def fingerprints(self, policy_id):
        with self._lock, self._conn() as c:
            rows = c.execute(
                "SELECT * FROM policy_fingerprints WHERE policy_id=? ORDER BY fingerprint_id DESC",
                (policy_id,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            for k in ("scenario_set", "seed_set", "behavior_features",
                      "response_signature", "feature_availability"):
                try:
                    d[k] = json.loads(d.get(k) or "{}")
                except Exception:
                    pass
            out.append(d)
        return out

    # ---- validations ----
    def add_validation(self, v):
        with self._lock, self._conn() as c:
            cur = c.execute(
                "INSERT INTO policy_validations(candidate_policy_id,reference_policy_id,"
                "artifact_same,semantic_difference,empirical_distance,feature_differences,"
                "multi_seed_stable,multi_scenario_stable,novelty_verdict,evaluation_role,"
                "evidence,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (v.candidate_policy_id, v.reference_policy_id,
                 int(v.artifact_same) if v.artifact_same is not None else None,
                 json.dumps(v.semantic_difference), v.empirical_distance,
                 json.dumps(v.feature_differences),
                 int(v.multi_seed_stable) if v.multi_seed_stable is not None else None,
                 int(v.multi_scenario_stable) if v.multi_scenario_stable is not None else None,
                 v.novelty_verdict, v.evaluation_role, json.dumps(v.evidence), v.created_at))
            c.commit()
            return cur.lastrowid

    def validations(self, candidate):
        with self._lock, self._conn() as c:
            rows = c.execute(
                "SELECT * FROM policy_validations WHERE candidate_policy_id=? "
                "ORDER BY validation_id DESC", (candidate,)).fetchall()
        return [dict(r) for r in rows]


_GLOBAL = None


def get_policy_repository():
    global _GLOBAL
    if _GLOBAL is None:
        _GLOBAL = PolicyRepository()
    return _GLOBAL
