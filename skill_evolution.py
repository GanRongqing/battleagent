#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""skill_evolution.py — MINIMAL, OFFLINE, AUDITABLE SKILL EVOLUTION PIPELINE.

The runtime Skill (skills/maritime_commander/SKILL.md) is IMMUTABLE during a game. This
pipeline evolves it OFFLINE, with external, auditable LLM discussion and versioned diffs:

  real evidence (audit A→F steps / evidence-file)
    → deterministic trigger / root-cause classification
    → ANALYST (LLM, external structured output)
    → CRITIC  (LLM, never sees Analyst hidden state, only its structured output)
    → EDITOR  (LLM, minimal candidate change or NO_CHANGE)
    → unified diff + sha256 (before/candidate)
    → static Skill audit (fair-play / scenario / truth-leakage)
    → cheap validation (schema + existing unit/fair-play tests + optional tiny regression)
    → approval gate (--approve, approved_by=operator; PENDING by default)
    → release (backup + install + versions.jsonl)  [only after explicit --approve]
    → rollback (--rollback <hash-or-version>)

Critical rule: SKILL_CHANGE_NOT_JUSTIFIED unless root cause includes STRATEGIC_DOCTRINE.
Runtime code bugs (tracking/allocator/simulator/logging/controller, stale LLM response,
stale terminal accounting) are NEVER treated as Skill problems.

No hidden chain-of-thought is ever requested or stored. Only external prompts, structured
outputs, evidence references, diffs, tests, approvals, and version metadata.

Usage:
  python skill_evolution.py --run-id <run> --step-id <step> [--run-regression]
  python skill_evolution.py --evidence-file <json>          [--run-regression]
  python skill_evolution.py --approve --evolution-id <id>
  python skill_evolution.py --rollback <hash-or-version>
  python skill_evolution.py --show <evolution_id>
"""
import argparse
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
SKILL_PATH = os.getenv("SKILL_EVOLUTION_SKILL_PATH",
                       os.path.join(ROOT, "skills", "maritime_commander", "SKILL.md"))
HISTORY_DIR = os.getenv("SKILL_EVOLUTION_HISTORY_DIR",
                        os.path.join(ROOT, "skills", "maritime_commander", "history"))
VERSIONS_FILE = os.path.join(HISTORY_DIR, "versions.jsonl")
RUNS_DIR = os.getenv("SKILL_EVOLUTION_RUNS_DIR", os.path.join(ROOT, "skill_evolution_runs"))
AUDIT_DIR = os.getenv("SKILL_EVOLUTION_AUDIT_DIR", os.path.join(ROOT, "runtime_audit"))

DS_URL = os.getenv("ANTHROPIC_BASE_URL", "https://api.deepseek.com/anthropic") + "/v1/messages"
DS_KEY = os.getenv("ANTHROPIC_AUTH_TOKEN", "")
DS_MODEL = os.getenv("ANTHROPIC_MODEL", "deepseek-v4-flash")

UNIT_TEST_FILES = [
    "test_v3_units.py", "test_v4_units.py", "test_v5_units.py", "test_v6_audit_units.py",
    "audit_variable_cardinality.py", "audit_scale_generalization.py",
]

from skill_evolution_prompts import (  # noqa: E402
    ANALYST_SYSTEM, ANALYST_USER_TEMPLATE,
    CRITIC_SYSTEM, CRITIC_USER_TEMPLATE,
    EDITOR_SYSTEM, EDITOR_USER_TEMPLATE,
)
import skill_evolution_validate as val  # noqa: E402

# ════════════════════════════════════════════════════════════════
# Evidence collection
# ════════════════════════════════════════════════════════════════
TRACK_SNAPSHOT_FIELDS = ("visible", "engaged", "assigned_usvs", "confidence",
                         "point_confidence", "age", "uncertainty", "predicted_position",
                         "is_ship", "maneuver_score")


def step_to_evidence(step_path, run_id):
    with open(step_path, "r", encoding="utf-8") as f:
        d = json.load(f)
    b = d.get("B_fused_state") or {}
    e = d.get("E_intermediate") or {}
    tracks = {}
    for n, t in (b.get("tracks") or {}).items():
        if not isinstance(t, dict):
            continue
        tracks[n] = {k: t.get(k) for k in TRACK_SNAPSHOT_FIELDS if k in t}
    a = d.get("A_raw_observation") or {}
    status = a.get("status") or {}
    return {
        "run_id": run_id,
        "step_id": d.get("audit_step_id"),
        "sim_time": d.get("sim_time"),
        "engine_result": status.get("对局结果"),
        "clean_result": None,
        "failure_category": None,
        "mission_state": b.get("mission"),
        "trigger": b.get("trigger"),
        "threat_clusters": b.get("clusters"),
        "coverage": b.get("coverage"),
        "track_beliefs": tracks,
        "commander_intent": e.get("intent"),
        "allocator_decision": e.get("allocator"),
        "controller_actions": e.get("controller"),
        "a_to_f_ref": os.path.relpath(step_path, ROOT),
        "metrics": {
            "lost_high_threat": len([t for t in tracks.values()
                                     if t.get("is_ship") and t.get("visible") is False]),
            "uncovered_ships": len([t for t in tracks.values()
                                    if t.get("is_ship") and not (t.get("assigned_usvs") or [])]),
        },
    }


def collect_evidence(run_id=None, step_id=None, evidence_file=None, max_items=6):
    items = []
    source = {}
    if evidence_file:
        with open(evidence_file, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, list):
            items = raw
        else:
            items = raw.get("evidence", [raw])
        source = {"type": "evidence-file", "path": os.path.relpath(evidence_file, ROOT)}
    elif run_id:
        run_dir = os.path.join(AUDIT_DIR, f"run_{run_id}")
        if not os.path.isdir(run_dir):
            raise SystemExit(f"audit run dir not found: {run_dir}")
        if step_id is not None:
            p = os.path.join(run_dir, f"step_{step_id}.json")
            if not os.path.exists(p):
                raise SystemExit(f"step file not found: {p}")
            items = [step_to_evidence(p, run_id)]
        else:
            steps = sorted(glob_step(run_dir))
            if not steps:
                raise SystemExit(f"no step files in {run_dir}")
            # representative subset: last step + any step with an applied LLM response
            picked = []
            for p in steps:
                try:
                    d = json.load(open(p, encoding="utf-8"))
                except Exception:
                    continue
                r = d.get("D_llm_response")
                if r and r.get("applied") is True:
                    picked.append(p)
            picked.append(steps[-1])
            seen = set()
            for p in picked:
                if p in seen:
                    continue
                seen.add(p)
                items.append(step_to_evidence(p, run_id))
                if len(items) >= max_items:
                    break
            if not items:
                items = [step_to_evidence(steps[-1], run_id)]
        source = {"type": "audit-run", "run_id": run_id, "step_id": step_id,
                  "dir": os.path.relpath(run_dir, ROOT)}
    else:
        raise SystemExit("provide --run-id/--step-id or --evidence-file")

    if not items:
        raise SystemExit("no evidence items extracted")
    for i, it in enumerate(items):
        it.setdefault("evidence_id", f"EVID-{i + 1:03d}")
    return {"source": source, "evidence": items}


def glob_step(run_dir):
    import glob
    return sorted(glob.glob(os.path.join(run_dir, "step_*.json")),
                  key=lambda p: int(os.path.basename(p).split("_")[1].split(".")[0]))


def evidence_brief(items):
    """Compact human/LLM-readable evidence bundle (no hidden truth)."""
    lines = []
    for it in items:
        lines.append(f"--- {it['evidence_id']} ---")
        for k in ("run_id", "step_id", "sim_time", "mission_state", "trigger",
                  "engine_result", "failure_category"):
            lines.append(f"{k}: {it.get(k)}")
        lines.append(f"coverage: {json.dumps(it.get('coverage'), ensure_ascii=False)}")
        lines.append("track_beliefs:")
        for n, t in (it.get("track_beliefs") or {}).items():
            lines.append(f"  {n}: visible={t.get('visible')} engaged={t.get('engaged')} "
                         f"assigned={t.get('assigned_usvs')} conf={t.get('confidence')} "
                         f"pc={t.get('point_confidence')} age={t.get('age')} "
                         f"unc={t.get('uncertainty')} pos={t.get('predicted_position')}")
        lines.append(f"commander_intent: {json.dumps(it.get('commander_intent'), ensure_ascii=False)}")
        lines.append(f"allocator: {json.dumps(it.get('allocator_decision'), ensure_ascii=False)}")
        lines.append(f"actions: {json.dumps((it.get('controller_actions') or {}).get('usv_actions'), ensure_ascii=False)[:800]}")
        lines.append(f"a_to_f_ref: {it.get('a_to_f_ref')}")
        lines.append(f"metrics: {json.dumps(it.get('metrics'), ensure_ascii=False)}")
    return "\n".join(lines)


# ════════════════════════════════════════════════════════════════
# Trigger / root-cause classification (deterministic + auditable)
# ════════════════════════════════════════════════════════════════
def classify_evidence(items):
    """Structured classification. SKILL_CHANGE_NOT_JUSTIFIED unless STRATEGIC_DOCTRINE."""
    categories = set()
    reasons = []
    for it in items:
        intent = it.get("commander_intent") or {}
        src = intent.get("source")
        if src in ("provider_fallback", "parse_fallback"):
            categories.add("CONTROLLER_EXECUTION")
            reasons.append(f"{it['evidence_id']}: LLM fallback ({src}) → runtime robustness, not doctrine")
        r = it.get("a_to_f_ref")
        tracks = it.get("track_beliefs") or {}
        lost_ships = [t for t in tracks.values()
                      if t.get("is_ship") and t.get("visible") is False]
        overcommit_lost = [t for t in lost_ships if len(t.get("assigned_usvs") or []) >= 3]
        uncovered = [t for t in tracks.values()
                     if t.get("is_ship") and not (t.get("assigned_usvs") or [])]
        cov = (it.get("coverage") or {}).get("quality")
        if overcommit_lost and cov is not None and cov < 0.4 and uncovered:
            categories.add("STRATEGIC_DOCTRINE")
            categories.add("RECON")
            reasons.append(
                f"{it['evidence_id']}: lost ship overcommitted (≥3 attackers) while "
                f"{len(uncovered)} ships uncovered at coverage={cov:.2f} → doctrine ambiguity "
                f"about information-before-commitment")
        elif cov is not None and cov < 0.3:
            categories.add("RECON")
            reasons.append(f"{it['evidence_id']}: low coverage {cov:.2f}")
        if it.get("engine_result") == "Result.Defeat":
            categories.add("STRATEGIC_DOCTRINE")
            reasons.append(f"{it['evidence_id']}: defeat observed")
    if not categories:
        categories.add("RNG_OR_INCONCLUSIVE")
        reasons.append("no doctrine-relevant signal in evidence")
    primary = ("STRATEGIC_DOCTRINE" if "STRATEGIC_DOCTRINE" in categories
               else sorted(categories)[0])
    justified = "STRATEGIC_DOCTRINE" in categories
    return {
        "primary": primary,
        "categories": sorted(categories),
        "root_cause": "; ".join(reasons) if reasons else primary,
        "skill_change_justified": justified,
        "decision": "PROCEED" if justified else "SKILL_CHANGE_NOT_JUSTIFIED",
    }


# ════════════════════════════════════════════════════════════════
# LLM JSON call (external, structured output only, no CoT)
# ════════════════════════════════════════════════════════════════
def call_llm_json(system, user, call_fn=None, max_tokens=2500):
    """Return parsed JSON dict, or None on failure. Never stores secrets or CoT."""
    if call_fn is not None:
        text = call_fn(system, user)
    else:
        text = _default_llm_call(system, user, max_tokens=max_tokens)
    if not text:
        return None
    return extract_json_object(text)


def _default_llm_call(system, user, timeout=90, max_tokens=2500):
    import requests
    payload = {"model": DS_MODEL, "max_tokens": max_tokens,
               "thinking": {"type": "disabled"},
               "system": system,
               "messages": [{"role": "user", "content": user}]}
    try:
        resp = requests.post(DS_URL, headers={"x-api-key": DS_KEY,
                                              "anthropic-version": "2023-06-01",
                                              "content-type": "application/json"},
                             json=payload, timeout=timeout)
        if resp.status_code != 200:
            return None
        data = resp.json()
        return "".join(b.get("text", "") for b in data.get("content", [])
                       if b.get("type") == "text")
    except Exception:
        return None


def extract_json_object(text):
    if not text:
        return None
    s = text.strip()
    if s.startswith("```"):
        s = s.split("```", 2)[1] if s.count("```") >= 2 else s
        nl = s.find("\n")
        if nl != -1:
            s = s[nl + 1:]
    start = s.find("{")
    if start == -1:
        return None
    depth, in_str, esc = 0, False, False
    for i in range(start, len(s)):
        c = s[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(s[start:i + 1])
                    except Exception:
                        return None
    return None


# ════════════════════════════════════════════════════════════════
# Three external roles (1 Analyst + 1 Critic + 1 Editor, max 3 LLM calls)
# ════════════════════════════════════════════════════════════════
def run_analyst(skill, evidence, classification, call_fn=None):
    user = ANALYST_USER_TEMPLATE.format(skill=skill, evidence=evidence,
                                        classification=json.dumps(classification, ensure_ascii=False))
    obj = call_llm_json(ANALYST_SYSTEM, user, call_fn=call_fn, max_tokens=2500)
    if obj is None:
        return {"error": "analyst_llm_output_unparseable"}
    ok, err = val.validate_analyst_schema(obj)
    return obj if ok else {"error": f"analyst_schema_failed: {err}", "raw": obj}


def run_critic(skill, evidence, analyst_out, call_fn=None):
    if "error" in analyst_out:
        return {"error": "analyst_failed", "accept_analyst": False}
    user = CRITIC_USER_TEMPLATE.format(
        skill=skill, evidence=evidence,
        analyst=json.dumps(analyst_out, ensure_ascii=False))
    obj = call_llm_json(CRITIC_SYSTEM, user, call_fn=call_fn, max_tokens=2500)
    if obj is None:
        return {"error": "critic_llm_output_unparseable"}
    ok, err = val.validate_critic_schema(obj)
    return obj if ok else {"error": f"critic_schema_failed: {err}", "raw": obj}


def run_editor(skill, evidence, analyst_out, critic_out, call_fn=None):
    if "error" in analyst_out or "error" in critic_out:
        return {"error": "analyst_or_critic_failed"}
    user = EDITOR_USER_TEMPLATE.format(
        skill=skill, evidence=evidence,
        analyst=json.dumps(analyst_out, ensure_ascii=False),
        critic=json.dumps(critic_out, ensure_ascii=False))
    # Editor must return the FULL candidate skill inside one JSON field: needs a larger
    # token budget than the two diagnostic roles to avoid truncating the JSON mid-string.
    if call_fn is not None:
        raw = call_fn(EDITOR_SYSTEM, user)
    else:
        raw = _default_llm_call(EDITOR_SYSTEM, user, max_tokens=6000)
    obj = extract_json_object(raw) if raw else None
    if obj is None:
        return {"error": "editor_llm_output_unparseable",
                "raw_snippet": (raw or "")[:1500]}
    ok, err = val.validate_editor_schema(obj)
    return obj if ok else {"error": f"editor_schema_failed: {err}", "raw": obj}


# ════════════════════════════════════════════════════════════════
# Diff + release helpers
# ════════════════════════════════════════════════════════════════
def unified_diff(old, new, old_name="skill_before.md", new_name="skill_candidate.md"):
    return "".join(difflib.unified_diff(
        old.splitlines(keepends=True), new.splitlines(keepends=True),
        fromfile=old_name, tofile=new_name))


def read_text(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_text(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def run_dir_of(evolution_id):
    return os.path.join(RUNS_DIR, evolution_id)


# ════════════════════════════════════════════════════════════════
# Validation — cheap: schema + existing unit/fair-play tests + optional tiny regression
# ════════════════════════════════════════════════════════════════
def run_unit_tests(candidate_skill):
    """Install candidate temporarily, run existing test files, restore original."""
    backup = None
    if os.path.exists(SKILL_PATH):
        backup = read_text(SKILL_PATH)
    results = {}
    try:
        if backup is not None:
            write_text(SKILL_PATH, candidate_skill)
        for tf in UNIT_TEST_FILES:
            p = os.path.join(ROOT, tf)
            if not os.path.exists(p):
                results[tf] = {"rc": None, "pass": False, "note": "missing"}
                continue
            try:
                r = subprocess.run([sys.executable, p], cwd=ROOT, capture_output=True,
                                   timeout=240)
                results[tf] = {"rc": r.returncode, "pass": r.returncode == 0}
            except subprocess.TimeoutExpired:
                results[tf] = {"rc": None, "pass": False, "note": "timeout"}
    finally:
        if backup is not None:
            write_text(SKILL_PATH, backup)
    return {"pass": all(r.get("pass") for r in results.values()), "tests": results}


def _parse_meta(text):
    m = re.search(r"\[META\] result=(\S+)", text)
    result = m.group(1) if m else None
    def mf(key):
        mm = re.search(rf"\[META\].*?\b{key}=(\S+)", text)
        return mm.group(1) if mm else None
    return {
        "result": result,
        "victory_time": mf("victory_time"),
        "commander_source": mf("commander_source"),
        "commander_calls": mf("commander_calls"),
        "commander_parse_failures": mf("commander_parse_failures"),
        "commander_api_failures": mf("commander_api_failures"),
        "commander_policy_failures": mf("commander_policy_failures"),
        "commander_avg_latency": mf("commander_avg_latency"),
        "breakthrough": re.search(r"突破: (\d+)", text).group(1) if re.search(r"突破: (\d+)", text) else None,
    }


def run_tiny_regression(candidate_skill, scenarios, baseline=None):
    """3 cheap DEV scenarios with candidate installed; compare gross metrics to baseline."""
    if baseline is None:
        baseline = {}
    results = {}
    ok = True
    try:
        backup = read_text(SKILL_PATH) if os.path.exists(SKILL_PATH) else None
        if backup is not None:
            write_text(SKILL_PATH, candidate_skill)
        for sc in scenarios:
            name, wu, wuv, bu, buv, llm = sc
            results[name] = _run_one_game(name, wu, wuv, bu, buv, llm)
            meta = results[name].get("meta") or {}
            if not results[name].get("run_success") or meta.get("result") in (None, "UNFINISHED"):
                ok = False
    finally:
        if backup is not None:
            write_text(SKILL_PATH, backup)
    return {"pass": ok, "scenarios": results, "baseline": baseline}


def _run_one_game(name, wu, wuv, bu, buv, llm):
    cfg = os.getenv("RW_CFG_FILE", "/tmp/opencode/rw_cfg.txt")
    log = os.path.join(ROOT, "logs_asy", f"skill_evo_{name}.log")
    try:
        os.makedirs(os.path.dirname(cfg), exist_ok=True)
        with open(cfg, "w", encoding="utf-8") as f:
            f.write(f"7 {wu} {wuv} {bu} {buv} fixed_frontage 1.0")
    except Exception:
        pass
    _http_get("/stop")
    time.sleep(2)
    env = dict(os.environ)
    env["SCENARIO_SCRIPT"] = "scenario_composition"
    env["LLM_ENABLED"] = "true" if llm else "false"
    env["PYTHONUNBUFFERED"] = "1"
    env.pop("ANTHROPIC_AUTH_TOKEN", None)
    if llm:
        env["ANTHROPIC_AUTH_TOKEN"] = _load_key()
    py = sys.executable
    try:
        t0 = time.time()
        proc = subprocess.Popen([py, os.path.join(ROOT, "agent_hybrid_v5.py"), "--uavs"],
                                cwd=ROOT, env=env, stdout=open(log, "w"),
                                stderr=subprocess.STDOUT)
        rc = proc.wait()
        wall = time.time() - t0
        text = open(log, encoding="utf-8", errors="replace").read()
        meta = _parse_meta(text)
        http_errors = len(re.findall(r"\[HTTP\].*异常|Traceback", text))
        return {"run_success": rc == 0 and "Traceback" not in text,
                "rc": rc, "wall": round(wall, 1), "meta": meta,
                "http_or_trace_errors": http_errors}
    except Exception as e:
        return {"run_success": False, "rc": None, "error": str(e), "meta": None}


def _http_get(path, timeout=8):
    import urllib.request
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000" + path, timeout=timeout) as r:
            return r.status
    except Exception:
        return None


def _load_key():
    try:
        return json.load(open(os.path.expanduser("~/.cline/data/secrets.json"))).get("deepSeekApiKey", "")
    except Exception:
        return ""


def api_alive():
    return _http_get("/status") is not None or _http_get("/result") is not None


# ════════════════════════════════════════════════════════════════
# Run directory + artifacts
# ════════════════════════════════════════════════════════════════
def write_artifacts(evolution_id, files):
    d = run_dir_of(evolution_id)
    os.makedirs(d, exist_ok=True)
    for name, data in files.items():
        if data is None:
            continue
        if isinstance(data, (dict, list)):
            val.dump_json(os.path.join(d, name), data)
        else:
            write_text(os.path.join(d, name), data)


# ════════════════════════════════════════════════════════════════
# Main pipeline
# ════════════════════════════════════════════════════════════════
def run_pipeline(run_id=None, step_id=None, evidence_file=None, evolution_id=None,
                 run_regression=False, approve=False, call_fn=None, scenarios=None):
    skill_before = read_text(SKILL_PATH) if os.path.exists(SKILL_PATH) else ""
    if not skill_before:
        raise SystemExit(f"SKILL.md not found at {SKILL_PATH}")
    old_hash = hashlib.sha256(skill_before.encode()).hexdigest()
    evolution_id = evolution_id or f"evo_{int(time.time())}"
    run_dir = run_dir_of(evolution_id)
    if os.path.exists(run_dir):
        raise SystemExit(f"evolution run already exists: {run_dir}")

    bundle = collect_evidence(run_id=run_id, step_id=step_id, evidence_file=evidence_file)
    classification = classify_evidence(bundle["evidence"])
    manifest = {
        "evolution_id": evolution_id,
        "created_at": time.time(),
        "source": bundle["source"],
        "evidence_ids": [it["evidence_id"] for it in bundle["evidence"]],
        "classification": classification,
        "status": classification["decision"],
        "old_skill_sha256": old_hash,
        "candidate_skill_sha256": None,
        "old_hash_prefix": old_hash[:12],
    }
    write_artifacts(evolution_id, {"manifest.json": manifest,
                                   "evidence.json": {"source": bundle["source"],
                                                     "evidence": bundle["evidence"]}})
    if not classification["skill_change_justified"]:
        write_artifacts(evolution_id, {"approval.json": {
            "status": "NOT_APPLICABLE", "evolution_id": evolution_id,
            "reason": classification["decision"],
            "evidence_refs": manifest["evidence_ids"]}})
        print(f"[skill_evolution] {classification['decision']} — "
              f"no doctrine-level justification (primary={classification['primary']})")
        return manifest

    evidence_txt = evidence_brief(bundle["evidence"])
    analyst = run_analyst(skill_before, evidence_txt, classification, call_fn=call_fn)
    write_artifacts(evolution_id, {"analyst_output.json": analyst})
    if "error" in analyst:
        manifest["status"] = "ANALYST_FAILED"
        write_artifacts(evolution_id, {"manifest.json": manifest})
        print(f"[skill_evolution] analyst failed: {analyst.get('error')}")
        return manifest

    critic = run_critic(skill_before, evidence_txt, analyst, call_fn=call_fn)
    write_artifacts(evolution_id, {"critic_output.json": critic})
    if "error" in critic:
        manifest["status"] = "CRITIC_FAILED"
        write_artifacts(evolution_id, {"manifest.json": manifest})
        print(f"[skill_evolution] critic failed: {critic.get('error')}")
        return manifest

    editor = run_editor(skill_before, evidence_txt, analyst, critic, call_fn=call_fn)
    write_artifacts(evolution_id, {"editor_output.json": editor})
    if "error" in editor:
        manifest["status"] = "EDITOR_FAILED"
        write_artifacts(evolution_id, {"manifest.json": manifest})
        print(f"[skill_evolution] editor failed: {editor.get('error')}")
        return manifest

    if editor.get("decision") == "NO_CHANGE":
        manifest["status"] = "NO_CHANGE"
        manifest["termination_reason"] = editor.get("termination_reason")
        write_artifacts(evolution_id, {"manifest.json": manifest,
                                       "skill_before.md": skill_before,
                                       "approval.json": {
                                           "status": "NOT_APPLICABLE", "evolution_id": evolution_id,
                                           "evidence_refs": editor.get("evidence_refs", []),
                                           "reason": "editor emitted NO_CHANGE"}})
        print(f"[skill_evolution] editor emitted NO_CHANGE: {editor.get('termination_reason')}")
        return manifest

    # MODIFY path
    candidate = editor.get("candidate_skill", "")
    if not candidate or candidate.strip() == "":
        manifest["status"] = "EDITOR_EMPTY_CANDIDATE"
        write_artifacts(evolution_id, {"manifest.json": manifest})
        return manifest
    if not candidate.endswith("\n"):
        candidate += "\n"  # normalize trailing newline (keeps diff minimal / file convention)
    candidate_hash = hashlib.sha256(candidate.encode()).hexdigest()
    diff = unified_diff(skill_before, candidate)
    audit = val.static_skill_audit(candidate, baseline_text=skill_before)
    manifest["candidate_skill_sha256"] = candidate_hash
    manifest["candidate_hash_prefix"] = candidate_hash[:12]
    manifest["diff_lines_changed"] = diff.count("\n")

    write_artifacts(evolution_id, {
        "manifest.json": manifest,
        "skill_before.md": skill_before,
        "skill_candidate.md": candidate,
        "skill.diff": diff,
        "static_audit.json": audit,
        "validation.json": {"status": "PENDING",
                            "schema": val.validate_all_schemas(analyst, critic, editor),
                            "unit_tests": None, "tiny_regression": None},
        "approval.json": {"status": "PENDING", "approved_by": None, "approved_at": None,
                          "evolution_id": evolution_id, "old_hash": old_hash,
                          "candidate_hash": candidate_hash,
                          "evidence_refs": editor.get("evidence_refs", []),
                          "old_hash_prefix": old_hash[:12],
                          "candidate_hash_prefix": candidate_hash[:12]},
    })
    if not audit["static_audit_pass"]:
        manifest["status"] = "STATIC_AUDIT_FAILED"
        write_artifacts(evolution_id, {"manifest.json": manifest})
        print(f"[skill_evolution] static audit FAILED: {audit['added_violations']}")
        return manifest

    # cheap validation
    unit = run_unit_tests(candidate)
    val_summary = {"status": "PENDING", "schema": val.validate_all_schemas(analyst, critic, editor),
                   "unit_tests": unit, "tiny_regression": None}
    if not unit["pass"]:
        val_summary["status"] = "UNIT_TESTS_FAILED"
        manifest["status"] = "VALIDATION_FAILED"
        write_artifacts(evolution_id, {"manifest.json": manifest, "validation.json": val_summary})
        print(f"[skill_evolution] unit tests FAILED: {[k for k, v in unit['tests'].items() if not v.get('pass')]}")
        return manifest

    if run_regression:
        sc = scenarios or [("regr_5v5_harness", 5, 5, 5, 5, False),
                           ("regr_10v10_harness", 10, 10, 10, 10, False),
                           ("regr_5v5_commander", 5, 5, 5, 5, True)]
        baseline = _collect_baseline()
        if not api_alive():
            regr = {"pass": False, "note": "sim services not reachable; regression NOT_RUN",
                    "scenarios": {}, "baseline": baseline}
        else:
            regr = run_tiny_regression(candidate, sc, baseline=baseline)
        val_summary["tiny_regression"] = regr
        if not regr.get("pass"):
            val_summary["status"] = "REGRESSION_FAILED"
            manifest["status"] = "VALIDATION_FAILED"
            write_artifacts(evolution_id, {"manifest.json": manifest, "validation.json": val_summary})
            print("[skill_evolution] tiny regression FAILED")
            return manifest
    else:
        regr = {"pass": None, "note": "skipped (pass --run-regression)",
                "scenarios": {}, "baseline": _collect_baseline()}
        val_summary["tiny_regression"] = regr

    val_summary["status"] = "VALIDATED"
    manifest["status"] = "STAGED"
    write_artifacts(evolution_id, {"manifest.json": manifest, "validation.json": val_summary})

    if approve:
        return do_approve_and_release(evolution_id, call_fn=call_fn)
    print(f"[skill_evolution] candidate staged (not released). Approve with: "
          f"python skill_evolution.py --approve --evolution-id {evolution_id}")
    return manifest


def _collect_baseline():
    base = {}
    for path, tag in (("logs_asy/smoke_harness_audit.log", "harness_5v5"),
                      ("logs_asy/smoke_deepseek_audit2.log", "commander_5v5")):
        p = os.path.join(ROOT, path)
        if os.path.exists(p):
            base[tag] = _parse_meta(read_text(p))
    return base


# ════════════════════════════════════════════════════════════════
# Approval + release + rollback
# ════════════════════════════════════════════════════════════════
def do_approve_and_release(evolution_id, call_fn=None):
    run_dir = run_dir_of(evolution_id)
    if not os.path.isdir(run_dir):
        raise SystemExit(f"evolution run not found: {run_dir}")
    approval = val.load_json(os.path.join(run_dir, "approval.json"))
    if approval.get("status") == "APPROVED":
        return approval
    candidate_path = os.path.join(run_dir, "skill_candidate.md")
    before_path = os.path.join(run_dir, "skill_before.md")
    if not os.path.exists(candidate_path) or not os.path.exists(before_path):
        raise SystemExit("no staged candidate (no skill_candidate.md / skill_before.md)")
    candidate = read_text(candidate_path)
    before = read_text(before_path)
    old_hash = hashlib.sha256(before.encode()).hexdigest()
    cand_hash = hashlib.sha256(candidate.encode()).hexdigest()

    approval.update({"status": "APPROVED", "approved_by": "operator",
                     "approved_at": time.time(), "evolution_id": evolution_id,
                     "old_hash": old_hash, "candidate_hash": cand_hash})
    val.dump_json(os.path.join(run_dir, "approval.json"), approval)
    _release(evolution_id, before, candidate, old_hash, cand_hash, approval)
    print(f"[skill_evolution] APPROVED + RELEASED evolution_id={evolution_id} "
          f"old={old_hash[:12]} new={cand_hash[:12]}")
    return approval


def _release(evolution_id, before, candidate, old_hash, cand_hash, approval):
    os.makedirs(HISTORY_DIR, exist_ok=True)
    backup_path = os.path.join(HISTORY_DIR, f"SKILL_{old_hash[:12]}.md")
    if not os.path.exists(backup_path):
        write_text(backup_path, before)
    # install candidate
    write_text(SKILL_PATH, candidate)
    version = 1
    records = []
    if os.path.exists(VERSIONS_FILE):
        for ln in open(VERSIONS_FILE, encoding="utf-8"):
            ln = ln.strip()
            if ln:
                try:
                    records.append(json.loads(ln))
                except Exception:
                    pass
        if records:
            version = max(int(r.get("version", 0)) for r in records) + 1
    record = {
        "version": version,
        "timestamp": time.time(),
        "evolution_id": evolution_id,
        "old_hash": old_hash,
        "new_hash": cand_hash,
        "old_hash_prefix": old_hash[:12],
        "new_hash_prefix": cand_hash[:12],
        "evidence_refs": approval.get("evidence_refs", []),
        "validation_result": "VALIDATED",
        "rollback_target": old_hash,
    }
    with open(VERSIONS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    release = {"status": "RELEASED", "version": version,
               "old_hash": old_hash, "new_hash": cand_hash,
               "backup": os.path.relpath(backup_path, ROOT),
               "rollback_target": old_hash,
               "installed_at": time.time()}
    val.dump_json(os.path.join(run_dir_of(evolution_id), "release.json"), release)
    # update manifest status
    man = val.load_json(os.path.join(run_dir_of(evolution_id), "manifest.json"))
    man["status"] = "RELEASED"
    man["release_version"] = version
    val.dump_json(os.path.join(run_dir_of(evolution_id), "manifest.json"), man)


def rollback(target):
    if not os.path.exists(VERSIONS_FILE):
        raise SystemExit("no version history found")
    records = []
    for ln in open(VERSIONS_FILE, encoding="utf-8"):
        ln = ln.strip()
        if ln:
            try:
                records.append(json.loads(ln))
            except Exception:
                pass
    rec = None
    for r in records:
        if str(target) in (r.get("new_hash", ""), r.get("new_hash_prefix", ""),
                           str(r.get("version"))):
            rec = r
            break
    if rec is None:
        raise SystemExit(f"rollback target not found: {target}")
    old_hash = rec["rollback_target"]
    backup_path = os.path.join(HISTORY_DIR, f"SKILL_{old_hash[:12]}.md")
    ev_dir = run_dir_of(rec["evolution_id"])
    if os.path.exists(backup_path):
        old = read_text(backup_path)
    elif os.path.exists(os.path.join(ev_dir, "skill_before.md")):
        old = read_text(os.path.join(ev_dir, "skill_before.md"))
    else:
        raise SystemExit(f"no rollback source found for {old_hash[:12]}")
    write_text(SKILL_PATH, old)
    now_hash = hashlib.sha256(old.encode()).hexdigest()
    assert now_hash == old_hash, f"rollback integrity check failed: {now_hash} != {old_hash}"
    print(f"[skill_evolution] rolled back to {old_hash[:12]} (version {rec.get('version')}) — "
          f"SKILL.md restored exactly")
    return {"status": "ROLLED_BACK", "to_hash": old_hash, "version": rec.get("version"),
            "evolution_id": rec.get("evolution_id")}


# ════════════════════════════════════════════════════════════════
# --show
# ════════════════════════════════════════════════════════════════
def show_trace(evolution_id):
    d = run_dir_of(evolution_id)
    if not os.path.isdir(d):
        raise SystemExit(f"evolution run not found: {d}")
    def load(name, default=None):
        p = os.path.join(d, name)
        return val.load_json(p) if os.path.exists(p) else default
    man = load("manifest.json", {})
    ev = load("evidence.json", {})
    ana = load("analyst_output.json")
    cri = load("critic_output.json")
    edi = load("editor_output.json")
    audit = load("static_audit.json")
    vald = load("validation.json")
    appr = load("approval.json")
    rel = load("release.json")

    print("=== SKILL EVOLUTION TRACE ===")
    print("EVOLUTION ID:", evolution_id)
    print("TRIGGER:", json.dumps(man.get("classification", {}), ensure_ascii=False))
    print("\nEVIDENCE")
    for it in (ev.get("evidence") or []):
        print(f"  {it.get('evidence_id')} run={it.get('run_id')} step={it.get('step_id')} "
              f"sim={it.get('sim_time')} mission={it.get('mission_state')} "
              f"trigger={it.get('trigger')} cov={(it.get('coverage') or {}).get('quality')} "
              f"ref={it.get('a_to_f_ref')}")
    print("ROOT CAUSE:", man.get("classification", {}).get("root_cause"))
    print("\nANALYST")
    print("  " + json.dumps(ana, ensure_ascii=False) if ana else "  NOT RUN")
    print("\nCRITIC")
    print("  " + json.dumps(cri, ensure_ascii=False) if cri else "  NOT RUN")
    print("\nEDITOR")
    if edi:
        print("  decision:", edi.get("decision"))
        print("  accepted_suggestions:", json.dumps(edi.get("accepted_suggestions"), ensure_ascii=False))
        print("  rejected_suggestions:", json.dumps(edi.get("rejected_suggestions"), ensure_ascii=False))
        print("  change_summary:", edi.get("change_summary"))
        print("  termination_reason:", edi.get("termination_reason"))
    print("SKILL BEFORE HASH:", man.get("old_skill_sha256"))
    print("\nDIFF")
    diffp = os.path.join(d, "skill.diff")
    if os.path.exists(diffp):
        print(read_text(diffp))
    print("CANDIDATE HASH:", man.get("candidate_skill_sha256"))
    print("STATIC AUDIT:", json.dumps(audit, ensure_ascii=False) if audit else "NOT RUN")
    print("VALIDATION:", json.dumps(vald, ensure_ascii=False) if vald else "NOT RUN")
    print("APPROVAL:", json.dumps({k: appr.get(k) for k in ("status", "approved_by", "approved_at")} if appr else {}, ensure_ascii=False))
    print("RELEASE VERSION:", (rel or {}).get("version"))
    print("ROLLBACK TARGET:", (rel or man).get("rollback_target") or man.get("old_skill_sha256"))


# ════════════════════════════════════════════════════════════════
def main(argv=None):
    ap = argparse.ArgumentParser(description="Minimal offline auditable Skill evolution")
    ap.add_argument("--run-id", help="runtime audit run id (runtime_audit/run_<id>)")
    ap.add_argument("--step-id", type=int, help="audit step id within run")
    ap.add_argument("--evidence-file", help="evidence JSON file")
    ap.add_argument("--evolution-id", help="evolution run id (default auto timestamp)")
    ap.add_argument("--run-regression", action="store_true",
                    help="run tiny regression smoke (needs sim services)")
    ap.add_argument("--approve", action="store_true",
                    help="explicitly approve + release the staged candidate")
    ap.add_argument("--rollback", help="hash or version to roll back to")
    ap.add_argument("--show", help="evolution id to print trace for")
    args = ap.parse_args(argv)

    if args.show:
        show_trace(args.show)
        return 0
    if args.rollback:
        rollback(args.rollback)
        return 0
    if args.approve:
        if not args.evolution_id:
            raise SystemExit("--approve requires --evolution-id")
        do_approve_and_release(args.evolution_id)
        return 0
    run_pipeline(run_id=args.run_id, step_id=args.step_id,
                 evidence_file=args.evidence_file, evolution_id=args.evolution_id,
                 run_regression=args.run_regression, approve=args.approve)
    return 0


if __name__ == "__main__":
    sys.exit(main())
