#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_version_memory.py — Part A unit tests (A1-A9)."""
import hashlib
import json
import os
import subprocess
import sys

VM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(VM))


def load(name):
    return json.load(open(os.path.join(VM, "cards", name, "MECHANISM_CARD.json"), encoding="utf-8"))


def man(name):
    return json.load(open(os.path.join(VM, "cards", name, "VERSION_MANIFEST.json"), encoding="utf-8"))


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def test_A1_schema_validation():
    r = subprocess.run([sys.executable, os.path.join(VM, "tools", "validate_card.py"),
                        os.path.join(VM, "cards", "W5", "MECHANISM_CARD.json"),
                        os.path.join(VM, "cards", "ACE", "MECHANISM_CARD.json"),
                        os.path.join(VM, "cards", "C2", "MECHANISM_CARD.json")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_A2_hash_correct():
    assert man("ACE")["sha256"] == sha(os.path.join(ROOT, "agent_hybrid_allocator_expand.py"))
    assert man("C2")["sha256"] == sha(os.path.join(ROOT, "agent_hybrid_lock_geometry.py"))


def test_A3_lineage_correct():
    assert load("ACE")["parent_id"] == "W5"
    assert load("C2")["parent_id"].startswith("white-combat-0002-v1")
    assert man("ACE")["parent_sha256"] == man("W5")["sha256"]


def test_A4_changed_functions_detected():
    assert "ExpandingAllocator.allocate_usvs" in " ".join(man("ACE")["changed_functions"]) or \
           any("allocate_usvs" in f for f in man("ACE")["changed_functions"])
    assert any("step" in f for f in man("C2")["changed_functions"])


def test_A5_interface_change_detection():
    # all current candidates declare no interface changes
    assert man("W5")["interface_changes"] == []
    assert man("ACE")["interface_changes"] == []
    assert man("C2")["interface_changes"] == []


def test_A6_semantic_diff_generated():
    for n in ("W5", "ACE", "C2"):
        p = os.path.join(VM, "cards", n, "SEMANTIC_DIFF.md")
        assert os.path.exists(p) and os.path.getsize(p) > 50


def test_A7_w5_vs_ace():
    r = subprocess.run([sys.executable, os.path.join(VM, "tools", "compare_versions.py"),
                        "--base", "W5", "--candidate", "ACE"], capture_output=True, text=True)
    assert r.returncode == 0 and "CONDITIONAL_RESERVE_RELEASE" in r.stdout


def test_A8_ace_vs_c2():
    r = subprocess.run([sys.executable, os.path.join(VM, "tools", "compare_versions.py"),
                        "--base", "ACE", "--candidate", "C2"], capture_output=True, text=True)
    assert r.returncode == 0 and "LOCK_FIRST_APPROACH" in r.stdout


def test_A9_runtime_untouched():
    # W5/ACE/C2 sha unchanged from frozen values
    assert sha(os.path.join(ROOT, "agent_hybrid_v5.py")) == \
        "e823e7bed219f4693aa778a838df1400c161f8e7e44001502e5bceb0ae804252"
    assert sha(os.path.join(ROOT, "agent_hybrid_allocator_expand.py")) == man("ACE")["sha256"]
    assert sha(os.path.join(ROOT, "agent_hybrid_lock_geometry.py")) == man("C2")["sha256"]


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t(); print("PASS", t.__name__)
        except Exception as e:
            failed += 1; print("FAIL", t.__name__, ":", e)
    print("=" * 40)
    print("PASS" if failed == 0 else "FAIL", f"{len(tests)-failed}/{len(tests)}")
    sys.exit(1 if failed else 0)
