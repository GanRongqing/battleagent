#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_skill_evolution.py — offline Skill-evolution pipeline unit tests.

All tests run against TEMP skill/history/runs paths (never the real SKILL.md) and use
injected fake LLM call functions (no provider, no simulator). Validates:

  immutability during runtime, evidence refs, role schemas, non-doctrine gating,
  staged-not-released, static audit, approval install, version record, rollback, --show.

Run: python test_skill_evolution.py
"""
import contextlib
import io
import json
import os
import sys
import tempfile
import time

_TPL = tempfile.mkdtemp(prefix="skill_evo_test_")
os.environ["SKILL_EVOLUTION_SKILL_PATH"] = os.path.join(_TPL, "SKILL.md")
os.environ["SKILL_EVOLUTION_HISTORY_DIR"] = os.path.join(_TPL, "history")
os.environ["SKILL_EVOLUTION_RUNS_DIR"] = os.path.join(_TPL, "runs")
os.environ["SKILL_EVOLUTION_AUDIT_DIR"] = os.path.join(_TPL, "audit")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import skill_evolution as se                          # noqa: E402
import skill_evolution_validate as val                # noqa: E402
import skill_evolution_prompts as prompts             # noqa: E402

PASS = []
FAIL = []


def check(name, cond, detail=""):
    if cond:
        PASS.append(name)
        print(f"  [PASS] {name}")
    else:
        FAIL.append(name)
        print(f"  [FAIL] {name} {detail}")


OLD_SKILL = ("# Maritime Commander Skill\n\n## Mission\n\nPrevent breakthrough.\n"
             "Maintain information coverage before aggressive commitment.\n")
CANDIDATE_SKILL = OLD_SKILL + (
    "\nWhen a committed track becomes uncertain while the mission remains unresolved, "
    "prefer restoring coverage before increasing concentration, unless immediate "
    "breakthrough risk dominates.\n")


def doctrine_evidence_file():
    ev = {"source": {"type": "test"}, "evidence": [{
        "evidence_id": "EVID-001", "run_id": "test_run", "step_id": 336,
        "sim_time": 6598.0, "engine_result": None, "clean_result": None,
        "mission_state": "NORMAL_COMBAT", "trigger": "lost_high_threat",
        "coverage": {"quality": 0.16, "cells_covered": 10, "cells_total": 56},
        "track_beliefs": {
            "black_usv3": {"is_ship": True, "visible": False, "engaged": False,
                           "assigned_usvs": ["white_usv1", "white_usv2", "white_usv5"],
                           "confidence": 0.5, "point_confidence": 0.5, "age": 64.0,
                           "uncertainty": 6880.0, "predicted_position": [194044.6, 402435.1]},
            "black_usv4": {"is_ship": True, "visible": True, "engaged": False,
                           "assigned_usvs": [], "confidence": 1.0, "point_confidence": 1.0,
                           "age": 0.0, "uncertainty": 4000.0,
                           "predicted_position": [196103.7, 436549.3]},
        },
        "commander_intent": {"source": "deepseek", "describe": "posture=balanced "
                             "reserve_ratio=0.10 uav_mode=focused_reacquire"},
        "allocator_decision": {"result": {}, "margin": None, "candidates": []},
        "controller_actions": {"usv_actions": [], "uav_actions": []},
        "a_to_f_ref": "audit/run_test/step_336.json",
        "metrics": {"lost_high_threat": 1, "uncovered_ships": 1},
    }]}
    p = os.path.join(_TPL, "evidence_doctrine.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(ev, f, ensure_ascii=False)
    return p


def non_doctrine_evidence_file():
    ev = {"source": {"type": "test"}, "evidence": [{
        "evidence_id": "EVID-001", "run_id": "test_run", "step_id": 1,
        "sim_time": 100.0, "engine_result": None, "mission_state": "NORMAL_COMBAT",
        "trigger": "periodic", "coverage": {"quality": 0.9},
        "track_beliefs": {"black_usv1": {"is_ship": True, "visible": True,
                                         "assigned_usvs": ["white_usv1"]}},
        "commander_intent": {"source": "provider_fallback", "describe": "fallback"},
        "allocator_decision": {"result": {}, "margin": None},
        "controller_actions": {"usv_actions": []},
        "a_to_f_ref": "audit/run_test/step_1.json",
        "metrics": {"lost_high_threat": 0, "uncovered_ships": 0},
    }]}
    p = os.path.join(_TPL, "evidence_nondoctrine.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(ev, f, ensure_ascii=False)
    return p


def fake_call_fn():
    """Role-dispatching fake LLM: returns canned structured JSON per role.

    Dispatch on distinctive Chinese role markers (the role system prompts cross-reference
    each other, e.g. EDITOR text mentions ANALYST/CRITIC, so ASCII words are ambiguous).
    """
    def fn(system, user):
        if "编辑器" in system:
            return json.dumps({
                "role": "editor", "decision": "MODIFY", "evidence_refs": ["EVID-001"],
                "accepted_suggestions": ["add uncertainty-before-concentration guidance"],
                "rejected_suggestions": [],
                "change_summary": "clarify restore-coverage-before-concentration on "
                                  "uncertain committed tracks",
                "expected_effect": "avoid overcommitment to lost tracks",
                "possible_side_effects": ["slightly later reinforcement"],
                "termination_reason": "single small clarification sufficient",
                "candidate_skill": CANDIDATE_SKILL})
        if "审查员" in system:
            return json.dumps({
                "role": "critic", "evidence_refs": ["EVID-001"], "accept_analyst": True,
                "counterexamples": [], "overfit_risks": [],
                "constraint_conflicts": [], "recommended_changes": [],
                "confidence": 0.6})
        if "分析师" in system:
            return json.dumps({
                "role": "analyst", "evidence_refs": ["EVID-001"],
                "root_cause": "lost-track overcommit while coverage low → "
                              "information-before-commitment ambiguity",
                "skill_change_needed": True,
                "problematic_doctrine": ["Low-confidence commitment"],
                "proposed_principles": ["When a committed track becomes uncertain and "
                                        "mission unresolved, prefer restoring coverage "
                                        "before increasing concentration."],
                "expected_effect": "less wasted commitment on lost tracks",
                "risk": "possible under-commitment in fast threats",
                "scope": "general", "confidence": 0.7})
        return None
    return fn


def fresh_temp_skill():
    with open(os.environ["SKILL_EVOLUTION_SKILL_PATH"], "w", encoding="utf-8") as f:
        f.write(OLD_SKILL)


def read_skill():
    with open(os.environ["SKILL_EVOLUTION_SKILL_PATH"], encoding="utf-8") as f:
        return f.read()


# ── 1. runtime immutability ──
def test_skill_immutable_during_runtime():
    print("== test_skill_immutable_during_runtime ==")
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "agent_hybrid_v5.py"), encoding="utf-8").read()
    # no write-mode open on SKILL.md anywhere in the agent
    import re
    write_opens = re.findall(
        r"open\([^)]*SKILL\.md[^)]*,\s*[\"'][wa][\"']", src)
    check("agent has no write-mode open on SKILL.md", not write_opens, str(write_opens))
    check("agent does not call replace/copy/rename to SKILL.md",
          "SKILL.md" not in re.findall(r"(os\.replace|shutil\.copy|os\.rename)\([^)]*\)", src) or
          "SKILL.md" not in src)
    check("SkillLoader is read-only",
          "open(self.path, \"r\"" in src or "open(self.path, 'r'" in src or "open(path, \"r\"" in src)


# ── 2. evidence references ──
def test_evolution_evidence_references():
    print("== test_evolution_evidence_references ==")
    bundle = se.collect_evidence(evidence_file=doctrine_evidence_file())
    ids = [it["evidence_id"] for it in bundle["evidence"]]
    check("evidence items carry EVID ids", ids == ["EVID-001"], str(ids))
    calls = {}
    def spy(system, user):
        calls["user"] = user
        return json.dumps({"role": "analyst", "evidence_refs": ["EVID-001"],
                           "root_cause": "x", "skill_change_needed": True,
                           "problematic_doctrine": [], "proposed_principles": [],
                           "expected_effect": "", "risk": "", "scope": "general",
                           "confidence": 0.5})
    out = se.run_analyst(OLD_SKILL, se.evidence_brief(bundle["evidence"]),
                         {"primary": "STRATEGIC_DOCTRINE"}, call_fn=spy)
    check("analyst prompt contains evidence_id", "EVID-001" in calls.get("user", ""))
    check("analyst output cites evidence_refs", out.get("evidence_refs") == ["EVID-001"])


# ── 3-5. schemas ──
def test_analyst_schema():
    print("== test_analyst_schema ==")
    good = {"role": "analyst", "evidence_refs": ["EVID-001"], "root_cause": "x",
            "skill_change_needed": True, "problematic_doctrine": [], "proposed_principles": [],
            "expected_effect": "", "risk": "", "scope": "general", "confidence": 0.5}
    ok, err = val.validate_analyst_schema(good)
    check("analyst schema accepts valid output", ok, err)
    ok2, _ = val.validate_analyst_schema({"role": "analyst", "evidence_refs": []})
    check("analyst schema rejects missing fields", not ok2)


def test_critic_schema():
    print("== test_critic_schema ==")
    good = {"role": "critic", "evidence_refs": ["EVID-001"], "accept_analyst": True,
            "counterexamples": [], "overfit_risks": [], "constraint_conflicts": [],
            "recommended_changes": [], "confidence": 0.6}
    ok, err = val.validate_critic_schema(good)
    check("critic schema accepts valid output", ok, err)
    ok2, _ = val.validate_critic_schema({"role": "critic"})
    check("critic schema rejects missing fields", not ok2)


def test_editor_schema():
    print("== test_editor_schema ==")
    good = {"role": "editor", "decision": "MODIFY", "evidence_refs": ["EVID-001"],
            "accepted_suggestions": [], "rejected_suggestions": [],
            "change_summary": "s", "expected_effect": "e", "possible_side_effects": [],
            "termination_reason": "t", "candidate_skill": CANDIDATE_SKILL}
    ok, err = val.validate_editor_schema(good)
    check("editor schema accepts MODIFY with candidate", ok, err)
    bad = dict(good)
    bad["decision"] = "NO_CHANGE"
    ok2, _ = val.validate_editor_schema(bad)  # NO_CHANGE without candidate is valid
    check("editor schema accepts NO_CHANGE without candidate", ok2)
    ok3, _ = val.validate_editor_schema({"role": "editor", "decision": "MODIFY"})
    check("editor schema rejects MODIFY without candidate", not ok3)


# ── 6. non-doctrine gating ──
def test_no_skill_change_for_non_doctrine_bug():
    print("== test_no_skill_change_for_non_doctrine_bug ==")
    fresh_temp_skill()
    ev = non_doctrine_evidence_file()
    cls = se.classify_evidence(se.collect_evidence(evidence_file=ev)["evidence"])
    check("provider fallback → SKILL_CHANGE_NOT_JUSTIFIED",
          cls["decision"] == "SKILL_CHANGE_NOT_JUSTIFIED", str(cls))
    called = {"n": 0}
    def fn(system, user):
        called["n"] += 1
        return "{}"
    man = se.run_pipeline(evidence_file=ev, evolution_id="evo_nondoctrine_test",
                          call_fn=fn)
    check("pipeline stops without calling any role",
          man["status"] == "SKILL_CHANGE_NOT_JUSTIFIED" and called["n"] == 0, str(called))
    check("no candidate produced",
          not os.path.exists(os.path.join(se.run_dir_of("evo_nondoctrine_test"),
                                          "skill_candidate.md")))


# ── 7. staged-not-released ──
def test_candidate_does_not_overwrite_before_approval():
    print("== test_candidate_does_not_overwrite_before_approval ==")
    fresh_temp_skill()
    old_text = read_skill()
    old_hash = val.sha256_text(old_text)
    se.run_pipeline(evidence_file=doctrine_evidence_file(),
                    evolution_id="evo_stage_test", call_fn=fake_call_fn())
    check("SKILL.md unchanged before approval", read_skill() == old_text)
    check("candidate staged in run dir",
          os.path.exists(os.path.join(se.run_dir_of("evo_stage_test"),
                                      "skill_candidate.md")))
    appr = val.load_json(os.path.join(se.run_dir_of("evo_stage_test"), "approval.json"))
    check("approval PENDING by default", appr.get("status") == "PENDING")
    man = val.load_json(os.path.join(se.run_dir_of("evo_stage_test"), "manifest.json"))
    check("old_skill_sha256 recorded", man.get("old_skill_sha256") == old_hash)
    check("candidate_skill_sha256 recorded", bool(man.get("candidate_skill_sha256")))


# ── 8-9. static audit ──
def test_static_audit_rejects_enemy_count_hardcode():
    print("== test_static_audit_rejects_enemy_count_hardcode ==")
    bad = CANDIDATE_SKILL + "\nAssume the enemy always fields exactly 15 ships.\n"
    r = val.static_skill_audit(bad, baseline_text=OLD_SKILL)
    check("static audit rejects fixed enemy count",
          r["static_audit_pass"] is False and any(
              v.get("added") for v in r["violations"]), str(r["violations"]))


def test_static_audit_rejects_scenario_specific_rule():
    print("== test_static_audit_rejects_scenario_specific_rule ==")
    bad = CANDIDATE_SKILL + "\nIn the 10v10 scenario, use 3 attackers per target.\n"
    r = val.static_skill_audit(bad, baseline_text=OLD_SKILL)
    check("static audit rejects scenario label",
          r["static_audit_pass"] is False and any(
              v.get("added") and v["pattern"] == "scenario_size_label"
              for v in r["violations"]), str(r["violations"]))


# ── 10-12. approval / version / rollback ──
def _stage_for_approval(evo_id):
    fresh_temp_skill()
    se.run_pipeline(evidence_file=doctrine_evidence_file(), evolution_id=evo_id,
                    call_fn=fake_call_fn())
    return read_skill()


def test_approval_installs_candidate():
    print("== test_approval_installs_candidate ==")
    old_text = _stage_for_approval("evo_approve_test")
    cand_text = read_text(os.path.join(se.run_dir_of("evo_approve_test"),
                                       "skill_candidate.md"))
    cand_hash = val.sha256_text(cand_text)
    appr = se.do_approve_and_release("evo_approve_test")
    check("approval status APPROVED by operator",
          appr.get("status") == "APPROVED" and appr.get("approved_by") == "operator")
    check("SKILL.md now equals candidate", read_skill() == cand_text)
    check("candidate hash matches installed skill",
          val.sha256_text(read_skill()) == cand_hash)


def test_version_record_written():
    print("== test_version_record_written ==")
    _stage_for_approval("evo_version_test")
    se.do_approve_and_release("evo_version_test")
    records = []
    with open(os.environ["SKILL_EVOLUTION_HISTORY_DIR"] + "/versions.jsonl",
              encoding="utf-8") as f:
        for ln in f:
            if ln.strip():
                records.append(json.loads(ln))
    check("versions.jsonl has at least one release record", len(records) >= 1)
    rec = records[-1]
    check("latest record is this evolution",
          rec.get("evolution_id") == "evo_version_test", str(rec.get("evolution_id")))
    check("version record fields complete",
          all(k in rec for k in ("version", "timestamp", "old_hash", "new_hash",
                                 "evolution_id", "evidence_refs", "validation_result",
                                 "rollback_target")))
    check("rollback_target == old_hash",
          rec["rollback_target"] == rec["old_hash"])


def test_rollback_restores_old_skill_exactly():
    print("== test_rollback_restores_old_skill_exactly ==")
    old_text = _stage_for_approval("evo_rollback_test")
    se.do_approve_and_release("evo_rollback_test")
    check("skill is candidate after release", read_skill() != old_text)
    se.rollback("1")  # version 1
    check("rollback restores exact old skill", read_skill() == old_text)
    check("old skill hash verified",
          val.sha256_text(read_skill()) == val.sha256_text(old_text))


# ── 13. --show ──
def test_evolution_show_trace():
    print("== test_evolution_show_trace ==")
    _stage_for_approval("evo_show_test")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        se.show_trace("evo_show_test")
    out = buf.getvalue()
    check("show prints evolution trace header", "SKILL EVOLUTION TRACE" in out)
    check("show prints evidence + role sections",
          all(s in out for s in ("EVOLUTION ID", "EVIDENCE", "ROOT CAUSE", "ANALYST",
                                 "CRITIC", "EDITOR", "DIFF", "STATIC AUDIT", "VALIDATION",
                                 "APPROVAL", "RELEASE VERSION", "ROLLBACK TARGET")))


def read_text(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def main():
    tests = [test_skill_immutable_during_runtime,
             test_evolution_evidence_references,
             test_analyst_schema,
             test_critic_schema,
             test_editor_schema,
             test_no_skill_change_for_non_doctrine_bug,
             test_candidate_does_not_overwrite_before_approval,
             test_static_audit_rejects_enemy_count_hardcode,
             test_static_audit_rejects_scenario_specific_rule,
             test_approval_installs_candidate,
             test_version_record_written,
             test_rollback_restores_old_skill_exactly,
             test_evolution_show_trace]
    for t in tests:
        try:
            t()
        except Exception as e:
            FAIL.append(t.__name__)
            print(f"  [ERROR] {t.__name__}: {e}")
        except SystemExit as e:
            FAIL.append(t.__name__)
            print(f"  [ERROR] {t.__name__}: SystemExit({e})")
    print("=" * 60)
    print(f"PASS: {len(PASS)}  FAIL: {len(FAIL)}")
    if FAIL:
        print("FAILED:", FAIL)
    return 0 if not FAIL else 1


if __name__ == "__main__":
    sys.exit(main())
