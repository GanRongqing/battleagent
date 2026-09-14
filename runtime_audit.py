#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""runtime_audit.py — per-step A→F runtime audit persistence for agent_hybrid_v5.py.

Captures, for every complete Agent decision round (audit_step_id), the six evidence
layers:

  A  raw legal HTTP observation     /status + /legal_actions (+ /obs if ever used)
  B  fused state                    tracks(confidence/age/uncertainty) + resource +
                                     mission + clusters + coverage summary + state_sig
  C  exact external LLM request     system + user payload actually sent to DeepSeek
  D  raw external LLM response      raw provider text + parsed intent + latency/error
  E  validated intent + allocator   StrategicIntent + allocator result/candidates/margin
                                     + controller result
  F  execution feedback             post-ActionSafety actions + exact /apply payload +
                                     response + next-step feedback link

Security / policy:
  - NEVER logs API keys / secrets.
  - NEVER stores hidden model chain-of-thought (provider thinking is disabled and only
    text-type content blocks are captured by call_commander_llm).
  - Pure instrumentation: does not change any decision, policy, or simulation logic.
  - Opt-in via AUDIT_ENABLED=1 (default off) so production runs are unaffected.

Output layout (per run):
  runtime_audit/run_<run_id>/step_<audit_step_id>.json   (one JSON per decision round)
  runtime_audit/run_<run_id>/manifest.json               (step -> file map)

LLM responses are asynchronous (commander background thread): the C/D records are
APPENDED to the step file of the *source* step (the decision round that spawned the
request), identified by audit_step_id + request_id, so an auditor can always rebuild
A→F for the step that originated a Commander call.

Replay:  python audit_step_replay.py --run-id <id> --step-id <id>
"""
import json
import os
import threading
import time

AUDIT_ENABLED = os.getenv("AUDIT_ENABLED", "0").strip().lower() in ("1", "true", "yes")
AUDIT_DIR = os.getenv("AUDIT_DIR", "runtime_audit")
# Optional cap on per-payload raw observation bytes stored (0 = unlimited).
AUDIT_MAX_RAW = int(os.getenv("AUDIT_MAX_RAW", "0") or "0")


def _truncate(obj, limit):
    """Truncate JSON payload to `limit` bytes (0 = no limit). Returns (payload, truncated)."""
    if not limit:
        return obj, None
    s = json.dumps(obj, ensure_ascii=False)
    if len(s) <= limit:
        return obj, None
    cut = s[:limit]
    return json.loads(cut), len(s)


class StepAudit:
    """Manager: owns the run directory, step counter, and async append thread-safety."""

    def __init__(self, run_id="pending", base_dir=AUDIT_DIR, enabled=AUDIT_ENABLED):
        self.enabled = enabled
        self.base_dir = base_dir
        self.run_id = run_id
        self.step_id = 0
        self._lock = threading.Lock()
        self._manifest = {}

    # ── lifecycle ──
    def set_run_id(self, run_id):
        self.run_id = run_id
        if self.enabled and run_id:
            os.makedirs(self._run_dir(), exist_ok=True)

    def _run_dir(self):
        return os.path.join(self.base_dir, f"run_{self.run_id}")

    def path_for(self, step_id):
        return os.path.join(self._run_dir(), f"step_{step_id}.json")

    def new_step(self, sim_time, wall_time):
        """Open a new decision round. Returns a StepRecord (or None when disabled)."""
        if not self.enabled:
            return None
        with self._lock:
            prev = self.step_id
            self.step_id += 1
        rec = StepRecord(self, self.step_id, prev, sim_time, wall_time)
        return rec

    # ── persistence ──
    def write(self, rec):
        """Full write of a step record at finalize.

        Merges into any existing on-disk state: non-None fields of `rec` overwrite,
        None fields are preserved. This is required because the Commander background
        thread may append C/D (async LLM) to a step file BEFORE the main thread
        finalizes that step — a blind overwrite would destroy the appended evidence.
        """
        with self._lock:
            self._manifest[str(rec.step_id)] = os.path.basename(rec.path)
            d = {}
            if os.path.exists(rec.path):
                try:
                    with open(rec.path, "r", encoding="utf-8") as f:
                        d = json.load(f)
                except Exception:
                    d = {}
            for k, v in rec.d.items():
                if v is not None:
                    d[k] = v
            self._write_json(rec.path, d)
            self._write_manifest()

    def append(self, step_id, section, data):
        """Append a late-arriving section (async LLM C/D) to an existing step file."""
        if not self.enabled:
            return
        with self._lock:
            path = self.path_for(step_id)
            d = {}
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        d = json.load(f)
                except Exception:
                    d = {}
            if section == "C":
                d["C_llm_request"] = data
            elif section == "D":
                d["D_llm_response"] = data
            self._write_json(path, d)

    def _write_json(self, path, d):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=1)
        except Exception:
            pass

    def _write_manifest(self):
        if not self.enabled:
            return
        try:
            with open(os.path.join(self._run_dir(), "manifest.json"), "w",
                      encoding="utf-8") as f:
                json.dump(self._manifest, f, ensure_ascii=False, indent=1)
        except Exception:
            pass

    def flush_manifest(self):
        self._write_manifest()


class StepRecord:
    """Mutable per-round evidence record; finalize() persists it."""

    def __init__(self, audit, step_id, prev_step_id, sim_time, wall_time):
        self.audit = audit
        self.step_id = step_id
        self.prev_step_id = prev_step_id
        self.path = audit.path_for(step_id)
        self.d = {
            "run_id": audit.run_id,
            "audit_step_id": step_id,
            "prev_audit_step_id": prev_step_id,
            "sim_time": round(float(sim_time), 3),
            "wall_time": wall_time,
            "A_raw_observation": {"status": None, "obs": None, "legal_actions": None,
                                  "truncated": []},
            "B_fused_state": {},
            "C_llm_request": None,
            "D_llm_response": None,
            "E_intermediate": {"intent": None, "allocator": None, "controller": None},
            "F_execution_feedback": {"requested_actions": None, "filtered_actions": None,
                                     "apply_payload": None, "apply_response": None,
                                     "feedback_link": None},
        }

    # ── A: raw legal observation ──
    def set_A(self, status_raw, obs_raw, legal_raw):
        a = self.d["A_raw_observation"]
        if status_raw is not None:
            a["status"], tr = _truncate(status_raw, AUDIT_MAX_RAW)
            if tr:
                a["truncated"].append({"field": "status", "dropped_bytes": tr})
        a["obs"] = obs_raw  # /obs defined but currently unused by Agent (None)
        if legal_raw is not None:
            a["legal_actions"], tr = _truncate(legal_raw, AUDIT_MAX_RAW)
            if tr:
                a["truncated"].append({"field": "legal_actions", "dropped_bytes": tr})

    # ── B: fused state ──
    def set_B(self, **kwargs):
        self.d["B_fused_state"] = kwargs

    # ── E: intermediate (intent + allocator + controller) ──
    def set_E(self, **kwargs):
        for k, v in kwargs.items():
            self.d["E_intermediate"][k] = v

    # ── F: execution feedback ──
    def set_F(self, **kwargs):
        for k, v in kwargs.items():
            self.d["F_execution_feedback"][k] = v

    def finalize(self):
        self.audit.write(self)
        return self.step_id


def record_intent(intent):
    """Serializable StrategicIntent summary (describe string, no secrets)."""
    if intent is None:
        return None
    try:
        return {"describe": intent.describe(),
                "reason": getattr(intent, "reason", "")[:500]}
    except Exception:
        return {"describe": repr(intent)[:1000]}


def serialize_track(t, now):
    """Serializable EnemyTrack snapshot (fused belief, not runtime truth)."""
    if t is None:
        return None
    pos = t.predicted_position(now) if hasattr(t, "predicted_position") else None
    try:
        age = t.age(now) if hasattr(t, "age") else None
        unc = t.uncertainty(now) if hasattr(t, "uncertainty") else None
    except Exception:
        age, unc = None, None
    return {
        "name": t.name,
        "is_ship": getattr(t, "is_ship", None),
        "confidence": round(getattr(t, "confidence", 0.0), 3),
        "point_confidence": round(getattr(t, "point_confidence", 0.0), 3),
        "maneuver_score": round(getattr(t, "maneuver_score", 0.0), 3),
        "age": round(age, 1) if age is not None else None,
        "uncertainty": round(unc, 1) if unc is not None else None,
        "predicted_position": [round(pos[0], 1), round(pos[1], 1)] if pos else None,
        "last_velocity": list(getattr(t, "last_velocity", []) or []),
        "last_seen_time": round(getattr(t, "last_seen_time", 0.0), 1),
        "visible": t.is_visible(now) if hasattr(t, "is_visible") else None,
        "engaged": getattr(t, "engaged", False),
        "assigned_usvs": sorted(getattr(t, "assigned_usvs", set()) or []),
        "has_position": getattr(t, "has_position", False),
    }


def serialize_resource(rs):
    if rs is None:
        return None
    try:
        return {
            "usv_total": rs.usv_total, "usv_alive": rs.usv_alive,
            "usv_available": rs.usv_available, "usv_engaged": rs.usv_engaged,
            "usv_frozen": rs.usv_frozen,
            "available_ratio": round(rs.available_ratio, 3),
            "engaged_ratio": round(rs.engaged_ratio, 3),
            "frozen_ratio": round(rs.frozen_ratio, 3),
            "uav_alive": rs.uav_alive, "uav_airborne": rs.uav_airborne,
            "uav_searching": rs.uav_searching, "uav_screening": rs.uav_screening,
            "uav_reacquiring": rs.uav_reacquiring, "uav_returning": rs.uav_returning,
            "uav_charging": rs.uav_charging,
            "available_sensing_ratio": round(rs.available_sensing_ratio, 3),
            "active_combat_tracks": rs.active_combat_tracks,
            "lost_high_threat_tracks": rs.lost_high_threat_tracks,
            "threat_cluster_count": rs.threat_cluster_count,
            "coverage_quality": round(rs.coverage_quality, 3),
            "describe": rs.describe(),
        }
    except Exception:
        return {"describe": repr(rs)[:500]}


def serialize_cluster(c):
    if c is None:
        return None
    try:
        return {
            "id": c.id, "ships": c.ships, "visible": c.visible, "lost": c.lost,
            "avg_conf": round(c.avg_conf, 3), "min_x": int(c.min_x),
            "friendly_committed": c.friendly_committed,
            "local_force_ratio": round(c.local_force_ratio, 3),
            "near_break": c.near_break, "recon_coverage": c.recon_coverage,
            "describe": c.describe(),
        }
    except Exception:
        return {"describe": repr(c)[:500]}
