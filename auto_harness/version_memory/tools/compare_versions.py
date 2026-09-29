#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""compare_versions.py — print a mechanism-level comparison of two version cards.

Usage: python compare_versions.py --base W5 --candidate ACE
"""
import argparse
import json
import os

VM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(name):
    p = os.path.join(VM, "cards", name, "MECHANISM_CARD.json")
    return json.load(open(p, encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--candidate", required=True)
    a = ap.parse_args()
    b = load(a.base); c = load(a.candidate)
    print("=" * 60)
    print("VERSION COMPARISON")
    print("=" * 60)
    print(f"Parent:    {a.base}  ({b['candidate_id']})")
    print(f"Candidate: {a.candidate}  ({c['candidate_id']})")
    print(f"Changed files: {c['code'].get('changed_files')}")
    print(f"Changed functions: {c['code'].get('changed_functions')}")
    print(f"Interface changes: {c['code'].get('changed_files') and 'NONE' or 'NONE'}")
    print(f"Primary mechanism: {c['mechanism']['name']}")
    print(f"Failure addressed: {c['failure']['name']}")
    print(f"Mechanism evidence: {c['metrics'].get('mechanism_metrics')}")
    print(f"Combat evidence:    {c['metrics'].get('combat_metrics')}")
    print(f"Status: {c['status']}")
    for l in c.get("lessons", []):
        print(f"Reusable lesson: {l}")


if __name__ == "__main__":
    main()
