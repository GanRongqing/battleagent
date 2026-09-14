#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""audit_variable_cardinality.py — V5 变基数/路径泛化审计（只读，不修改）"""
import os
import re
import sys

ROOT = "/root/autodl-tmp/hsystem"
AGENT = os.path.join(ROOT, "agent_hybrid_v5.py")
SKILL = os.path.join(ROOT, "skills", "maritime_commander", "SKILL.md")
BUILDER = os.path.join(ROOT, "hsystem", "sim_script", "20250819TZB", "scenario_builder.py")


def read(p):
    try:
        return open(p, encoding="utf-8").read()
    except Exception:
        return ""


def audit():
    agent = read(AGENT)
    skill = read(SKILL)
    builder = read(BUILDER)
    runtime = agent.split("def selftest_trackmanager")[0]
    results = []

    def item(name, ok, detail=""):
        results.append((name, ok, detail))

    # fixed count assumptions
    fixed_usv = re.compile(r"(usv_total|usv_alive|uav_total|uav_alive|friendly)"
                           r"[^\n]{0,10}(==|= ?|>=|<=)[ ]*([5-9]|1[0-9]|2[0-9]|3[0-9])")
    item("No fixed friendly count in runtime", not fixed_usv.search(runtime),
         f"hits={fixed_usv.findall(runtime)[:3]}")
    fixed_ec = re.compile(r"(expected_enemy_count|num_black_usv\s*=|num_black_uav\s*=|"
                          r"enemy_count\s*=|black_usv_count)")
    item("No fixed enemy count / prior (TrackManager dynamic)", not fixed_ec.search(runtime),
         f"hits={fixed_ec.findall(runtime)[:3]}")
    item("No fixed reserve count (ratio only)",
         "reserve_ratio" in agent and "round(len(available) * ratio)" in agent)
    item("No fixed attacker count (marginal allocator)",
         "marginal_gain" in agent and "MIN_ASSIGN_VALUE" in agent)
    fixed_sector = re.compile(r"range\(\s*5\s*\)|\[0-9\]+ ?个扇区|idx ?- ?8")
    item("No fixed sector/fan count", not fixed_sector.search(runtime))

    # count-independent modules
    item("TrackManager count-independent",
         "for e in obs.active" in agent and "self.tracks[name] = EnemyTrack" in agent)
    item("Allocator count-independent (coverage floor + marginal)",
         "Pass 1：coverage floor" in agent and "target_value" in agent)
    item("UAVManager count-independent (demand roles)",
         "global_search" in agent and "reacquire_targets" in agent)
    item("USVController count-independent",
         "for u in obs.usvs:" in runtime and "for tname, t in tracks.items():" in runtime)
    item("Global reacquire count-independent",
         "MISSION_GLOBAL_REACQUIRE" in agent and "GLOBAL_REACQUIRE_DELAY" in agent)

    # commander label-blind
    item("Commander scenario-label blind",
         not re.search(r"(10v10|15v15|20v20|30v30|scenario_[a-z0-9]+)", skill)
         and not re.search(r"(SCENARIO=|scenario_label)", runtime))
    item("Commander path-label blind",
         "random_waypoint" not in skill and "waypoint" not in skill
         and "waypoint_seed" not in runtime.split("def selftest")[0])

    # fair-play
    bad = ["black_usv", "black_uav", "black_strategy", "BLACK_Y", "ENEMY_X",
           "260000", "vx=-10", "expected_enemy_count", "black_usv_count"]
    hits = []
    for b in bad:
        for i, line in enumerate(runtime.splitlines(), 1):
            if b in line and not line.strip().startswith("#"):
                hits.append((b, i))
    item("Fair-play runtime zero-hit", not hits, str(hits[:5]))

    # composition legality + frontage modes in builder
    item("Composition legality checker",
         "def validate_composition" in builder and "hangar capacity" in builder)
    item("Fixed-frontage + fixed-density deploy",
         "fixed_frontage" in builder and "fixed_density" in builder)

    print("=" * 60)
    print("=== VARIABLE CARDINALITY AUDIT ===")
    print("=" * 60)
    all_ok = True
    for name, ok, detail in results:
        all_ok = all_ok and ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        if not ok and detail:
            print(f"            -> {detail}")
    print("-" * 60)
    print(f"  FINAL: {'PASS' if all_ok else 'FAIL'} "
          f"({sum(1 for _, ok, _ in results if ok)}/{len(results)} checks)")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(audit())
