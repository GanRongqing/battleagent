#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""validate_card.py — lightweight schema validation for mechanism cards / version manifests.

Usage: python validate_card.py <card_or_manifest.json> [...]
Dependency-free (no jsonschema required); checks required keys + types per the schemas.
"""
import json
import sys

CARD_REQUIRED = ["candidate_id", "parent_id", "status", "code", "failure", "root_cause",
                 "mechanism", "applicability", "metrics", "validation", "limitations",
                 "lessons", "next_questions"]
MANIFEST_REQUIRED = ["candidate_id", "parent_id", "sha256", "changed_files",
                     "interface_changes", "behavior_scope", "mechanism_card"]


def validate(path):
    d = json.load(open(path, encoding="utf-8"))
    if "behavior_scope" in d and "mechanism_card" in d:
        req, kind = MANIFEST_REQUIRED, "manifest"
    else:
        req, kind = CARD_REQUIRED, "card"
    missing = [k for k in req if k not in d]
    if kind == "card":
        for k in ("code", "failure", "root_cause", "mechanism"):
            if k in d and not isinstance(d[k], dict):
                missing.append(f"{k}:not-object")
    if missing:
        print(f"FAIL {path}: missing/invalid {missing}")
        return 1
    print(f"OK   {path} ({kind})")
    return 0


if __name__ == "__main__":
    rc = 0
    for p in sys.argv[1:]:
        rc |= validate(p)
    sys.exit(rc)
