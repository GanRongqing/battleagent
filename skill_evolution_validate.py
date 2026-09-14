#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""skill_evolution_validate.py — static Skill audit + role-output schema validation.

Used by the offline skill_evolution.py pipeline. All checks are deterministic and
auditable. No simulator, no LLM.

Static Skill audit (fair-play / scenario / truth-leakage):
  - scans for scenario-size labels, fixed force counts, enemy-count assumptions,
    black-side runtime references, seed / waypoint assumptions, hidden truth references,
    and absolute force-allocation policies.
  - compares against the BASELINE: a pattern matched in an UNCHANGED baseline line is
    informational (e.g. the baseline's own fair-play prohibition text); a pattern matched
    in a NEW/ADDED line is a hard blocker (static_audit_pass=False).

Schema validation for the three role outputs (Analyst / Critic / Editor).
"""
import hashlib
import json
import re

FORBIDDEN_PATTERNS = [
    (r"(?i)\b(10v10|15v15|20v20|30v30)\b", "scenario_size_label"),
    (r"(?i)\b(5|10|15|20|30)\s+USVs?\b", "fixed_force_count_usv"),
    (r"(?i)\b(5|10|15|20|30)\s+UAVs?\b", "fixed_force_count_uav"),
    (r"(?i)\b(5|10|15|20|30)\s+艘\b", "fixed_force_count_cn"),
    (r"(?i)\bexpected_enemy_count\b", "expected_enemy_count"),
    (r"(?i)\bblack_usv\b", "black_runtime_usv"),
    (r"(?i)\bblack_uav\b", "black_runtime_uav"),
    (r"(?i)\bblack_strategy\b", "black_runtime_strategy"),
    (r"(?i)\bwaypoint_seed\b", "waypoint_seed"),
    (r"(?i)\bseed\s*[:=]?\s*\d+", "specific_seed_number"),
    (r"(?i)\bfixed enemy count\b", "fixed_enemy_count"),
    (r"(?i)\bfuture trajectory\b", "future_trajectory"),
    (r"(?i)\bground truth\b", "ground_truth"),
    (r"(?i)\bsimulator truth\b", "simulator_truth"),
    (r"(?i)\bexact hidden coordinates\b", "hidden_coordinates"),
    (r"(?i)\balways allocate exactly\s+\d+", "absolute_policy"),
    (r"(?i)\balways reserve exactly\s+\d+", "absolute_policy"),
    (r"(?i)\bexactly\s+\d+\s+(ships?|vessels?|units?|enemies?|usvs?|uavs?)\b", "absolute_force_count"),
    (r"(?i)\bfields?\s+(exactly\s+)?\d+\s+(enemy\s+)?(ships?|vessels?|units?|usvs?|uavs?)\b", "fixed_force_count"),
    (r"(?i)\b恰好(分配|保留)\s*\d+", "absolute_policy_cn"),
    (r"(?i)\b固定敌方数量\b", "fixed_composition_cn"),
    (r"(?i)\b(敌人|敌方)(总数|总兵力)\s*(为|是|等于|=)\s*\d+", "enemy_total_cn"),
]

ANALYST_REQUIRED = ["role", "evidence_refs", "root_cause", "skill_change_needed",
                    "problematic_doctrine", "proposed_principles", "expected_effect",
                    "risk", "scope", "confidence"]
CRITIC_REQUIRED = ["role", "evidence_refs", "accept_analyst", "counterexamples",
                   "overfit_risks", "constraint_conflicts", "recommended_changes",
                   "confidence"]
EDITOR_REQUIRED = ["role", "decision", "evidence_refs", "accepted_suggestions",
                   "rejected_suggestions", "change_summary", "expected_effect",
                   "possible_side_effects", "termination_reason"]


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _line_set(text):
    return {ln.strip() for ln in text.splitlines()}


def static_skill_audit(candidate_text, baseline_text=None):
    """Return {'static_audit_pass': bool, 'violations': [...], 'added_violations': [...]}.

    A pattern matched in a line that exists unchanged in `baseline_text` is reported as
    informational (baseline context, e.g. the fair-play prohibition text itself). A match
    in a line NOT present in the baseline (a new/changed line) is a hard blocker.
    """
    cand_lines = candidate_text.splitlines()
    base_set = _line_set(baseline_text) if baseline_text is not None else set()
    violations = []
    for ln in cand_lines:
        for pat, reason in FORBIDDEN_PATTERNS:
            if re.search(pat, ln):
                added = ln.strip() not in base_set
                violations.append({"line": ln, "pattern": reason, "added": added})
    added_violations = [v for v in violations if v.get("added")]
    return {
        "static_audit_pass": len(added_violations) == 0,
        "violations": violations,
        "added_violations": added_violations,
    }


def _require_str(v, key):
    return isinstance(v.get(key), str) and v.get(key).strip() != ""


def _require_list(v, key):
    return isinstance(v.get(key), list)


def _require_bool(v, key):
    return isinstance(v.get(key), bool)


def validate_analyst_schema(obj):
    if not isinstance(obj, dict):
        return False, "not a dict"
    for k in ANALYST_REQUIRED:
        if k not in obj:
            return False, f"missing key {k}"
    if obj.get("role") != "analyst":
        return False, "role != analyst"
    if not _require_str(obj, "root_cause") or not _require_list(obj, "evidence_refs"):
        return False, "root_cause str / evidence_refs list"
    if not _require_bool(obj, "skill_change_needed"):
        return False, "skill_change_needed bool"
    if not isinstance(obj.get("confidence"), (int, float)):
        return False, "confidence number"
    if obj.get("scope") not in ("general", "narrow"):
        return False, "scope must be general|narrow"
    return True, "ok"


def validate_critic_schema(obj):
    if not isinstance(obj, dict):
        return False, "not a dict"
    for k in CRITIC_REQUIRED:
        if k not in obj:
            return False, f"missing key {k}"
    if obj.get("role") != "critic":
        return False, "role != critic"
    if not _require_bool(obj, "accept_analyst"):
        return False, "accept_analyst bool"
    if not _require_list(obj, "evidence_refs") or not _require_list(obj, "counterexamples"):
        return False, "evidence_refs/counterexamples list"
    if not isinstance(obj.get("confidence"), (int, float)):
        return False, "confidence number"
    return True, "ok"


def validate_editor_schema(obj):
    if not isinstance(obj, dict):
        return False, "not a dict"
    for k in EDITOR_REQUIRED:
        if k not in obj:
            return False, f"missing key {k}"
    if obj.get("role") != "editor":
        return False, "role != editor"
    if obj.get("decision") not in ("MODIFY", "NO_CHANGE"):
        return False, "decision must be MODIFY|NO_CHANGE"
    if not _require_str(obj, "change_summary"):
        return False, "change_summary str"
    if obj.get("decision") == "MODIFY" and not _require_str(obj, "candidate_skill"):
        return False, "MODIFY requires candidate_skill"
    return True, "ok"


def validate_all_schemas(analyst, critic, editor):
    """Return {'pass': bool, 'errors': {...}}."""
    a_ok, a_err = validate_analyst_schema(analyst)
    c_ok, c_err = validate_critic_schema(critic)
    e_ok, e_err = validate_editor_schema(editor)
    return {
        "pass": a_ok and c_ok and e_ok,
        "errors": {"analyst": a_err, "critic": c_err, "editor": e_err},
    }


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
