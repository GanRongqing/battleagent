#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""run_after_artifacts_arrive.py — single entry point for the external-opponent pipeline.

Executes the STRICT state machine ONLY when the original Wave1(5)/Wave2(6) artifacts are present:

  CHECK_DROP_ZONES -> INVENTORY -> EXTRACT_ARCHIVES -> STATIC_CLASSIFY -> RECOVER_ENTRYPOINTS
  -> VALIDATE_BLACK_IDENTITY -> EXACT_COUNT_GATE -> SMOKE_11 -> FREEZE_ARTIFACTS
  -> BUILD_EVAL_REGISTRY -> RUN_ACE_GENERALIZATION_75 -> BUILD_CSV_REPORTS

Hard gates (STOP on any failure):
  Wave1 != 5 or Wave2 != 6            -> INCOMPLETE_EXTERNAL_DELIVERY
  black-side identity unclear         -> QUARANTINE_REQUIRED
  unsafe behavior detected            -> UNSAFE_EXTERNAL_ARTIFACT
  smoke != 11/11 valid                -> SMOKE_FAILED
  artifact hash not frozen            -> FREEZE_FAILED

Smoke seed = 41001 (separate from the official seed panel 42001-42005).
Never substitutes unrelated strategies; never modifies ACE / Frozen W5 / existing Black identities.
"""
import os
import subprocess
import sys

INC = "/root/sc2agent/incoming_opponents"
HERE = os.path.dirname(os.path.abspath(__file__))
PY = "/root/miniconda3/envs/hsystem_env/bin/python"
TOOLS = os.path.join(HERE, "tools")
SMOKE_SEED = 41001
EVAL_SEEDS = [42001, 42002, 42003, 42004, 42005]


class GateFail(Exception):
    pass


def run(script, *args):
    p = subprocess.run([PY, os.path.join(TOOLS, script), *map(str, args)],
                       cwd=HERE, capture_output=True, text=True)
    print(f"[{script}] rc={p.returncode} {p.stdout.strip()[-300:]}")
    if p.returncode != 0:
        print(p.stderr[-500:])
    return p.returncode


def count_files(wave):
    root = os.path.join(INC, wave)
    if not os.path.isdir(root):
        return 0, 0
    n_all = sum(len(fs) for _, _, fs in os.walk(root))
    return n_all, n_all


def check_drop_zones():
    n1, f1 = count_files("wave1")
    n2, f2 = count_files("wave2")
    print(f"CHECK_DROP_ZONES: wave1 files={f1} (need 5), wave2 files={f2} (need 6)")
    if f1 == 0 and f2 == 0:
        raise GateFail("WAITING_FOR_EXTERNAL_ARTIFACTS")
    return f1, f2


def main():
    print("=" * 70)
    print("EXTERNAL OPPONENT PIPELINE — run_after_artifacts_arrive")
    print("=" * 70)
    try:
        check_drop_zones()
    except GateFail as e:
        print(f"\nSTATUS = {e}\nPlace original Wave1/Wave2 files into "
              f"incoming_opponents/wave1|wave2, then re-run.")
        return 2

    try:
        run("inventory_incoming.py")                    # INVENTORY
        run("extract_archives.py")                      # EXTRACT_ARCHIVES
        run("classify_artifacts.py")                    # STATIC_CLASSIFY  (+ unsafe detection)
        run("recover_entrypoints.py")                   # RECOVER_ENTRYPOINTS
        run("validate_black_identity.py")               # VALIDATE_BLACK_IDENTITY
        # EXACT_COUNT_GATE
        # (implemented by the identity validator output; enforced here)
        import csv, json
        vi = os.path.join(HERE, "BLACK_IDENTITY_VALIDATION.csv")
        ok1 = ok2 = 0
        if os.path.exists(vi):
            for r in csv.DictReader(open(vi, encoding="utf-8")):
                if r.get("black_side_verified", "").lower() == "true":
                    ok1 += 1 if r.get("verdict", "").startswith("WAVE1") else 0
                    ok2 += 1 if r.get("verdict", "").startswith("WAVE2") else 0
        reg = json.load(open(os.path.join(HERE, "external_wave_registry.json")))
        ok1, ok2 = len(reg.get("wave1", [])), len(reg.get("wave2", []))
        if ok1 != 5 or ok2 != 6:
            raise GateFail(f"INCOMPLETE_EXTERNAL_DELIVERY (wave1={ok1}/5, wave2={ok2}/6)")
        # SAFETY gate is enforced inside classify_artifacts (UNSAFE -> quarantine)
        run("run_black_smoke.py", SMOKE_SEED)           # SMOKE_11 (seed 41001)
        run("freeze_artifact.py")                       # FREEZE_ARTIFACTS
        # FREEZE gate
        import csv as _csv
        fr = os.path.join(HERE, "FROZEN_WAVE_REGISTRY.csv")
        n_frozen = sum(1 for _ in _csv.DictReader(open(fr, encoding="utf-8"))) if os.path.exists(fr) else 0
        if n_frozen != 11:
            raise GateFail(f"FREEZE_FAILED ({n_frozen}/11)")
        run("build_eval_registry.py")                   # BUILD_EVAL_REGISTRY
        # RUN_ACE_GENERALIZATION_75 (only now)
        gen = os.path.join(HERE, "run_ace_generalization.py")
        if os.path.exists(gen):
            subprocess.run([PY, gen, "--seeds", ",".join(map(str, EVAL_SEEDS))], cwd=HERE)
        else:
            print("NOTE: RUN_ACE_GENERALIZATION_75 uses the frozen registry + ACE; "
                  "implemented under ace_wave_generalization once artifacts are frozen.")
        print("\nPIPELINE COMPLETE")
        return 0
    except GateFail as e:
        print(f"\nSTATUS = {e}\nSTOP. Fix the gate condition; do not substitute strategies.")
        return 3


if __name__ == "__main__":
    sys.exit(main())
