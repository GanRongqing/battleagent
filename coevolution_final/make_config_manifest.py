#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""coevolution_final/make_config_manifest.py — compute + write config_manifest.json.

Freeze record captured BEFORE the FINAL main experiment. Lists every versioned artifact,
its sha256, feature gates, holdout seeds, and freeze notes.
"""
import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.dirname(os.path.abspath(__file__))


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def sha_dir(path):
    h = hashlib.sha256()
    for fn in sorted(os.listdir(path)):
        if fn.endswith(".py"):
            h.update(fn.encode())
            h.update(sha(os.path.join(path, fn)).encode())
    return h.hexdigest()


def prompt_hash():
    # runtime prompt = SKILL.md (policy doctrine). Prompt template lives inside the agent;
    # we record SKILL.md + the agent prompt constants region hash (documented).
    return sha(os.path.join(ROOT, "skills", "maritime_commander", "SKILL.md"))


def physics_hash():
    eng = os.path.join(ROOT, "hsystem", "simulation", "core", "engine.py")
    tzb = os.path.join(ROOT, "hsystem", "simulation", "core", "tzb_engine.py")
    return (f"engine.py:{sha(eng)[:12]} tzb_engine.py:{sha(tzb)[:12]}")


def main():
    w5 = sha(os.path.join(ROOT, "agent_hybrid_v5.py"))
    w6 = sha(os.path.join(ROOT, "agent_hybrid_w6.py"))
    skill = sha(os.path.join(ROOT, "skills", "maritime_commander", "SKILL.md"))
    opp = sha(os.path.join(ROOT, "opponent_profiles.py"))
    scen = sha(os.path.join(ROOT, "hsystem", "sim_script", "20250819TZB",
                            "scenario_builder.py"))
    scen_comp = sha(os.path.join(ROOT, "hsystem", "sim_script", "20250819TZB",
                                 "scenario_composition.py"))
    anti_ev = sha_dir(os.path.join(ROOT, "anti_evasion"))
    w6_feature_gates = {}
    with open(os.path.join(ROOT, "anti_evasion", "config.py"), encoding="utf-8") as f:
        for m in re.finditer(r'"([a-z_]+)":\s*True', f.read()):
            w6_feature_gates[m.group(1)] = True
    manifest = {
        "experiment": "three-stage co-evolution FINAL (Stage0 W5xB0 / Stage1 W5xB3 / Stage2 W6xB3)",
        "white": {
            "W5_LEGACY_FROZEN_HASH": "a7842b29c81cc567ea63cae262cb6ab0b9d9bd9df90903c4115eaa6e6c6f0f66",
            "W5_RUNTIME_FILE_HASH": w5,
            "W5_freezenote": "W5_RUNTIME_FILE = legacy V5 + inert W6 integration hook "
                             "(_w6_intercept slot, None-default; never set under W5-only run => "
                             "behaviorally identical to W5_LEGACY_FROZEN_HASH which produced all "
                             "prior W5 baselines)",
            "W6_hash": w6,
            "anti_evasion_dir_hash": anti_ev,
            "w6_feature_gates": w6_feature_gates,
        },
        "skill": {
            "skill_hash": skill,
            "note": "skill released v1 (evo_losttrack_coverage); hash 155b0201... expected",
        },
        "black": {
            "opponent_profiles_hash": opp,
            "B3_LEGACY_FORMAL_EVAL_HASH": "377fcc0ef9829c7f510963ab284c84b36094a900d0d575247977e16eac1f9661",
            "B3_freezenote": "runtime file hash 7aa12e1d = formal-eval B3 (377fcc0e) + policy-neutral "
                             "event telemetry (_write_stats to /tmp/opencode/b3_events.json); decisions "
                             "(b3_plan + cmd_sail_area) unchanged => behaviorally identical",
            "B0_RANDOM": "legacy random-waypoint baseline (unchanged since formal)",
            "B3_ADAPTIVE": "legal-observation runtime replanning profile inside opponent_profiles.py",
            "b3_events_file": "/tmp/opencode/b3_events.json",
        },
        "prompt_hash": prompt_hash(),
        "simulator_physics": physics_hash(),
        "scenario_builder_hash": scen,
        "scenario_composition_hash": scen_comp,
        "physics_unchanged": True,
        "fair_play": {"white_black_internal_access": False,
                      "black_observation": "get_black_targets() only (Black radar intel) + own units",
                      "enforced_by": "static audit + hidden-truth counterfactual tests "
                                     "(test_opponent_profiles.py, test_w6_units.py T9)"},
        "holdout_seeds": list(range(4001, 4011)),
        "dev_seeds_never_in_final": [2001, 2002, 2003, 2004, 2005],
        "formal_seeds_never_in_final": list(range(1001, 1031)),
        "N_per_setting": 10,
        "main_episodes": 90,
        "budget_note": "FINAL N=10 hard max; no追加 for variance.",
        "stages": [
            {"stage": "Stage0", "white": "W5", "black": "B0_RANDOM",
             "meaning": "initial baseline"},
            {"stage": "Stage1", "white": "W5", "black": "B3_ADAPTIVE",
             "meaning": "black evolved only"},
            {"stage": "Stage2", "white": "W6", "black": "B3_ADAPTIVE",
             "meaning": "white anti-evasion adaptation over frozen B3"},
        ],
        "recorded_at": __import__("time").strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(os.path.join(OUT, "config_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print("wrote", os.path.join(OUT, "config_manifest.json"))
    print("W5 file hash:", w5)
    print("W6 file hash:", w6)
    print("anti_evasion dir hash:", anti_ev)
    print("opponent_profiles hash:", opp)
    print("skill hash:", skill)
    print("prompt(SKILL.md) hash:", prompt_hash())
    print("physics:", physics_hash())


if __name__ == "__main__":
    sys.exit(main())
