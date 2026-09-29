#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""build_mechanism_card.py — scaffold a mechanism card from code+parent (metadata only).

Usage: python build_mechanism_card.py --id white-combat-XXXX-v1 --parent ACE --file path.py
Prints a JSON template (does NOT write unless --write). No runtime effect.
"""
import argparse
import hashlib
import json
import os


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest() if os.path.exists(p) else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True)
    ap.add_argument("--parent", default=None)
    ap.add_argument("--file", required=True)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    card = {"candidate_id": a.id, "parent_id": a.parent, "status": "DRAFT", "created_at": "",
            "code": {"main_file": a.file, "sha256": sha(a.file), "parent_sha256": None,
                     "changed_files": [a.file], "changed_functions": [], "diff_path": None},
            "failure": {"name": "", "description": "", "evidence": []},
            "root_cause": {"name": "", "description": "", "confidence": ""},
            "mechanism": {"name": "", "summary": "", "trigger_condition": "", "behavior_change": "", "scope": ""},
            "applicability": {"required_conditions": [], "known_non_applicable_conditions": []},
            "metrics": {"mechanism_metrics": {}, "combat_metrics": {}},
            "validation": {"unit_tests": "", "dev_status": "", "fresh_status": ""},
            "limitations": [], "lessons": [], "next_questions": []}
    txt = json.dumps(card, indent=2, ensure_ascii=False)
    if a.write:
        d = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cards", a.id)
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "MECHANISM_CARD.json"), "w").write(txt)
        print("wrote", d)
    else:
        print(txt)


if __name__ == "__main__":
    main()
