#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""audit_step_replay.py — replay a single Agent decision round's A→F evidence.

Usage:
  python audit_step_replay.py --run-id <run_id> --step-id <audit_step_id>

Prints only the evidence that was actually persisted for that step. Any layer that is
missing (e.g. B/C/D/E not recorded, or the async LLM response had not yet been appended)
is printed as NOT RECORDED. This tool NEVER reconstructs missing data from future state —
it reads exactly one step file: runtime_audit/run_<run_id>/step_<audit_step_id>.json.

Optional:
  --dir <path>   runtime_audit base directory (default: ./runtime_audit)
  --json         dump the raw step file instead of the human-readable A→F view
"""
import argparse
import json
import os
import sys

AUDIT_DIR = "runtime_audit"


def load_step(run_id, step_id, base_dir):
    path = os.path.join(base_dir, f"run_{run_id}", f"step_{step_id}.json")
    if not os.path.exists(path):
        return None, path
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f), path


def _fmt(v, indent=2, width=110):
    if v is None:
        return None
    s = json.dumps(v, ensure_ascii=False, indent=indent)
    if len(s) > width:
        return s[:width] + "...(truncated)"
    return s


def _print_section(title, data):
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print('=' * 70)
    if data in (None, {}, []):
        print("  NOT RECORDED")
        return
    print(_fmt(data))


def main():
    ap = argparse.ArgumentParser(description="Replay one audited Agent decision round (A→F).")
    ap.add_argument("--run-id", required=True, help="audit run id (runtime_audit/run_<run-id>)")
    ap.add_argument("--step-id", required=True, help="audit_step_id (integer)")
    ap.add_argument("--dir", default=AUDIT_DIR, help="runtime_audit base directory")
    ap.add_argument("--json", action="store_true", help="dump raw step JSON")
    args = ap.parse_args()

    try:
        step_id = int(args.step_id)
    except ValueError:
        print(f"step-id must be an integer, got {args.step_id!r}")
        return 2

    rec, path = load_step(args.run_id, step_id, args.dir)
    if rec is None:
        print(f"Step not found: {path}")
        print("Available runs: " + ", ".join(
            d for d in sorted(os.listdir(args.dir)) if d.startswith("run_")) or "(none)")
        return 1

    if args.json:
        print(json.dumps(rec, ensure_ascii=False, indent=2))
        return 0

    meta = {k: rec.get(k) for k in ("run_id", "audit_step_id", "prev_audit_step_id",
                                    "sim_time", "wall_time")}
    print("=" * 70)
    print("  AUDIT STEP REPLAY (A→F)  —  only persisted evidence, no reconstruction")
    print("=" * 70)
    print(f"  run_id            = {meta.get('run_id')}")
    print(f"  audit_step_id     = {meta.get('audit_step_id')}")
    print(f"  prev_audit_step_id= {meta.get('prev_audit_step_id')}")
    print(f"  sim_time          = {meta.get('sim_time')}s")
    print(f"  wall_time         = {meta.get('wall_time')}")

    _print_section("A — RAW LEGAL HTTP OBSERVATION (/status, /legal_actions)",
                   rec.get("A_raw_observation"))
    _print_section("B — FUSED STATE (tracks / resource / mission / clusters / coverage)",
                   rec.get("B_fused_state"))
    _print_section("C — EXACT EXTERNAL LLM REQUEST (system + user sent to DeepSeek)",
                   rec.get("C_llm_request"))
    _print_section("D — RAW EXTERNAL LLM RESPONSE (raw text + parsed + latency/error)",
                   rec.get("D_llm_response"))
    _print_section("E — VALIDATED INTENT + ALLOCATOR (result/margin/candidates) + CONTROLLER",
                   rec.get("E_intermediate"))
    _print_section("F — EXECUTION FEEDBACK (post-safety actions + /apply payload/response)",
                   rec.get("F_execution_feedback"))
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
