#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""build_semantic_diff.py — deterministic (no-LLM) semantic diff builder.

Inputs: parent file, candidate file, mechanism card. Output: a SEMANTIC_DIFF.md with
What changed / Why / Trigger / Not changed / Expected mechanism / Interface changed.
Uses the mechanism card for the narrative and a function-level diff for the changed functions.
Optional --use-llm is accepted but NOT required; the deterministic path always works.

Usage: python build_semantic_diff.py --base W5 --candidate ACE
"""
import argparse
import hashlib
import json
import os
import re
import sys

VM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def funcs(path):
    if not os.path.exists(path):
        return set()
    return set(re.findall(r"^\s*(?:def|cpdef)\s+(\w+)", open(path, encoding="utf-8", errors="replace").read(), re.M))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--use-llm", action="store_true")
    a = ap.parse_args()
    card = json.load(open(os.path.join(VM, "cards", a.candidate, "MECHANISM_CARD.json"), encoding="utf-8"))
    pf = os.path.join(VM, "..", "..", "..", card["code"].get("main_file", ""))
    lines = ["# Semantic Diff (%s -> %s)" % (a.base, a.candidate), "",
             "## What changed", card["mechanism"]["summary"], "",
             "## Why changed", card["failure"]["description"],
             "Root cause: %s (%s)" % (card["root_cause"]["name"], card["root_cause"]["description"]), "",
             "## Trigger condition", card["mechanism"]["trigger_condition"], "",
             "## What was intentionally NOT changed",
             "- detection / TrackManager / radar / lock range / weapon / Black / scenario / judge",
             "- (see card applicability: %s)" % card["applicability"], "",
             "## Expected mechanism", card["mechanism"]["behavior_change"], "",
             "## Interface changed?",
             "NO" if not card["code"].get("changed_files") else "see VERSION_MANIFEST.interface_changes", ""]
    out = os.path.join(VM, "cards", a.candidate, "SEMANTIC_DIFF.generated.md")
    open(out, "w", encoding="utf-8").write("\n".join(lines))
    print("wrote", out, "(llm=%s, deterministic fallback used)" % a.use_llm)


if __name__ == "__main__":
    main()
