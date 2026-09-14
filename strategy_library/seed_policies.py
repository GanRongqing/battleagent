#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""strategy_library/seed_policies.py — register immutable B0-B3 policies (cards + artifacts)."""
import glob
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from strategy_library.policy_models import PolicyCard, ArtifactManifest, now  # noqa: E402
from strategy_library.policy_repository import get_policy_repository  # noqa: E402
from strategy_library.fingerprint import compute_fingerprint  # noqa: E402
from strategy_library.policy_compare import validate  # noqa: E402


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def env_sha():
    return sha(os.path.join(ROOT, "hsystem", "simulation", "core", "engine.py"))[:16] + ":" + \
        sha(os.path.join(ROOT, "hsystem", "simulation", "core", "tzb_engine.py"))[:16]


OPP = os.path.join(ROOT, "opponent_profiles.py")
OPP_HASH = sha(OPP)

CARDS = {
    "black-b0-v1": dict(version="1.0.0", side="black", strategy_family="random_maneuver",
        entry="scenario_builder random_waypoint (black_movement=random_waypoint)",
        intent={"pressure_objectives": ["random independent approach"], "target_priority": "none",
                "operational_goal": "random waypoint advance toward break line",
                "key_assumptions": [], "intended_failure_modes": ["predictable scatter",
                                                                  "no coordination"]},
        trig=[], strengths=["simple baseline", "cheap to run"], weaknesses=[
            ("no coordination or adaptivity", "declared"),
            ("does not exploit multi-axis pressure reliably", "inferred")],
        traits={"aggression": "moderate", "dispersion": "random", "coordination": "none",
                "adaptivity": "none", "recon_dependency": "none"},
        family="random_maneuver", role="historical_anchor", status="sealed",
        parent=None,
        description="Legacy random-waypoint baseline opponent (B0_RANDOM)"),
    "black-b1-v1": dict(version="1.0.0", side="black",
        strategy_family="multi_axis_penetration",
        entry="opponent_profiles.py spatial_groups/_multi_axis_paths (B1)",
        intent={"pressure_objectives": ["lateral multi-axis penetration"],
                "target_priority": "break-line corridors", "operational_goal": "spatial groups "
                "approach from several lateral lanes",
                "key_assumptions": [], "intended_failure_modes": ["group cohesion loss"]},
        trig=[], strengths=["explicit multi-axis spatial structure"], weaknesses=[
            ("no runtime adaptivity", "declared"), ("static group plans", "inferred")],
        traits={"aggression": "high", "dispersion": "grouped-multi-axis",
                "coordination": "spatial", "adaptivity": "none", "recon_dependency": "none"},
        role="general_opponent", status="active", parent=None,
        description="B1_MULTI_AXIS: dynamic spatial groups, multi-lateral approach"),
    "black-b2-v1": dict(version="1.0.0", side="black",
        strategy_family="coordinated_pressure",
        entry="opponent_profiles.py _coordinated_pressure_paths (B2)",
        intent={"pressure_objectives": ["synchronized coordinated pressure"],
                "target_priority": "break-line", "operational_goal": "group-synchronized lanes "
                "with staggered arrival", "key_assumptions": [],
                "intended_failure_modes": ["over-commit to fixed lanes"]},
        trig=[], strengths=["coordination + timing stagger"], weaknesses=[
            ("static once generated (no runtime replan)", "declared")],
        traits={"aggression": "high", "dispersion": "coordinated-lanes",
                "coordination": "high (static timetable)", "adaptivity": "none",
                "recon_dependency": "none"}, role="general_opponent", status="active",
        parent="black-b1-v1", description="B2_COORDINATED_PRESSURE"),
    "black-b3-v1": dict(version="1.0.0", side="black",
        strategy_family="adaptive_multi_axis_penetration",
        entry="opponent_profiles.py B3AdaptiveController/b3_plan (B3)",
        intent={"pressure_objectives": ["dispersion", "search burden", "adaptive evasion",
                                        "penetration"],
                "target_priority": "break-line", "operational_goal": "legal-observation-driven "
                "runtime replanning: lane shift away from detected White proximity (60km), "
                "evade > brute-force", "key_assumptions": ["White radar may reveal"],
                "intended_failure_modes": ["White early recon continuity",
                                           "concentration denial"]},
        trig=[{"trigger": "White detected within 60km of group centroid",
               "response": "lateral lane shift (replan)", "source": "code"},
              {"trigger": "15s interval tick", "response": "recompute lanes (anti-spam "
               "heading-change gate)", "source": "code"}],
        strengths=["adaptive evasion/dispersion", "raises exploration/resolution burden"],
        weaknesses=[("no offensive firepower increase vs B0 (evasion-oriented)", "declared"),
                    ("geometrically late against well-positioned interception (inferred from "
                     "FREE-reinforcement analyses)", "inferred")],
        traits={"aggression": "moderate", "dispersion": "high (adaptive)",
                "coordination": "high", "adaptivity": "high", "recon_dependency": "high"},
        role="stress_test", status="active", parent="black-b2-v1",
        description="B3_ADAPTIVE legal replanning opponent"),
}


def build_manifest(pid, entry):
    return ArtifactManifest(policy_id=pid, entrypoint=entry,
                            artifact_files=[os.path.relpath(OPP, ROOT)],
                            artifact_hash=sha(OPP),
                            opponent_module_hash=OPP_HASH,
                            environment_hash=env_sha(),
                            simulator_hash=env_sha())


def main():
    repo = get_policy_repository()
    ts = now()
    for pid, c in CARDS.items():
        card = PolicyCard(policy_id=pid, version=c["version"], side="black",
                          strategy_family=c["strategy_family"],
                          declared_intent=c["intent"], trigger_and_switch=c["trig"],
                          known_strengths=c["strengths"], known_weaknesses=c["weaknesses"],
                          declared_traits=c["traits"], status=c["status"],
                          evaluation_role=c["role"], parent_policy_id=c["parent"],
                          description=c["description"], created_at=ts, updated_at=ts)
        repo.upsert_card(card)
        m = build_manifest(pid, c["entry"])
        m.bundle_hash = m.compute_bundle()
        repo.upsert_artifact(m)
    # write cards json
    out = os.path.join(ROOT, "policy_system", "cards")
    os.makedirs(out, exist_ok=True)
    for pid in CARDS:
        json.dump(repo.get_card(pid), open(os.path.join(out, pid + ".json"), "w"),
                  ensure_ascii=False, indent=1)
    print("seeded cards:", list(CARDS))
    # fingerprint from available valid logs
    sets = {}
    for pid, d in {"black-b0-v1": os.path.join(ROOT, "logs_formal"),
                   "black-b3-v1": os.path.join(ROOT, "logs_opponent_formal")}.items():
        logs = glob.glob(os.path.join(d, "*.log"))
        sets[pid] = logs
        if logs:
            fp = compute_fingerprint(pid, logs)
            repo.add_fingerprint(fp)
    print("fingerprints:", {k: len(v) for k, v in sets.items()})
    # B1/B2: none valid -> mark unavailable by not computing (INSUFFICIENT in compare)
    # compare B0 vs B3
    if sets["black-b0-v1"] and sets["black-b3-v1"]:
        c0, c3 = repo.get_card("black-b0-v1"), repo.get_card("black-b3-v1")
        m0, m3 = repo.get_artifact("black-b0-v1"), repo.get_artifact("black-b3-v1")
        f0, f3 = repo.fingerprints("black-b0-v1")[0], repo.fingerprints("black-b3-v1")[0]
        v = validate(c0, m0, f0, c3, m3, f3)
        repo.add_validation(v)
        print("B0 vs B3 validation:", v.novelty_verdict, "dist", v.empirical_distance)
    print("bundles:", {pid: repo.get_artifact(pid)["bundle_hash"][:12] for pid in CARDS})


if __name__ == "__main__":
    sys.exit(main())
