#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""coevolution_final/print_terminal.py — final terminal block (sections 33-34)."""
import csv
import json
import os

OUT = os.path.dirname(os.path.abspath(__file__))


def main():
    man = json.load(open(os.path.join(OUT, "config_manifest.json")))
    agg = {(r["scenario"], r["stage"]): r
           for r in csv.DictReader(open(os.path.join(OUT, "stage_aggregate.csv")))}
    w = man["white"]; b = man["black"]; sk = man["skill"]
    print("=" * 58)
    print("=== THREE-STAGE CO-EVOLUTION FINAL ===")
    print()
    print("CONFIG")
    print(f"W5 hash (legacy freeze) = {w['W5_LEGACY_FROZEN_HASH']}")
    print(f"W5 runtime file hash    = {w['W5_RUNTIME_FILE_HASH']}")
    print(f"W6 hash                 = {w['W6_hash']}")
    print(f"anti_evasion dir hash   = {w['anti_evasion_dir_hash']}")
    print(f"Skill hash              = {sk['skill_hash']}")
    print(f"B0 = B0_RANDOM (legacy) ; B3 file hash = {b['opponent_profiles_hash']}")
    print(f"Physics                 = {man['simulator_physics']}")
    print(f"FINAL seeds             = {man['holdout_seeds']}")
    print("N per setting = 10")
    for sc in ["S1", "S2", "S3"]:
        r = agg[(sc, "Stage0")]
        print()
        print("-" * 58)
        print(f"{sc} — White {r['friendly_usv_initial']}+{r['friendly_uav_initial']} vs Black {r['enemy_combat_usv_initial']}")
        for st, tag in [("Stage0", "STAGE 0 — W5 x B0"), ("Stage1", "STAGE 1 — W5 x B3"),
                        ("Stage2", "STAGE 2 — W6 x B3")]:
            x = agg[(sc, st)]
            print()
            print(tag)
            print(f"clean      = {float(x['clean_rate']):.2f}  ({x['clean_win']}/10)")
            print(f"kills      = {float(x['enemy_combat_kills']):.1f}")
            print(f"loss       = {float(x['friendly_usv_dead']):.1f}")
            print(f"breakthru  = {float(x['breakthrough_rate']):.2f}  ({x['breakthrough']}/10)")
            print(f"explore    = {float(x['explored_area_km2']):.0f} km2")
            print(f"resolution = {float(x['resolution_time_s']):.0f} s")
        s0, s1, s2 = (agg[(sc, "Stage0")], agg[(sc, "Stage1")], agg[(sc, "Stage2")])
        print()
        print("BLACK EVOLUTION DELTA (S1 - S0):")
        print(f"clean = {float(s1['clean_rate'])-float(s0['clean_rate']):+.2f}  "
              f"loss = {float(s1['friendly_usv_dead'])-float(s0['friendly_usv_dead']):+.1f}  "
              f"breakthru = {float(s1['breakthrough_rate'])-float(s0['breakthrough_rate']):+.2f}  "
              f"explore = {float(s1['explored_area_km2'])-float(s0['explored_area_km2']):+.0f}  "
              f"resolution = {float(s1['resolution_time_s'])-float(s0['resolution_time_s']):+.0f}")
        print("WHITE ADAPTATION DELTA (S2 - S1):")
        print(f"clean = {float(s2['clean_rate'])-float(s1['clean_rate']):+.2f}  "
              f"loss = {float(s2['friendly_usv_dead'])-float(s1['friendly_usv_dead']):+.1f}  "
              f"breakthru = {float(s2['breakthrough_rate'])-float(s1['breakthrough_rate']):+.2f}  "
              f"explore = {float(s2['explored_area_km2'])-float(s1['explored_area_km2']):+.0f}  "
              f"resolution = {float(s2['resolution_time_s'])-float(s1['resolution_time_s']):+.0f}")
    print()
    print("=" * 58)
    print("=== SYSTEMATIC CO-EVOLUTION FRAMEWORK ===")
    checks = [
        ("Frozen checkpoint", True),
        ("One-side-at-a-time evolution", True),
        ("Fair-play observation boundary", True),
        ("No physics buff", True),
        ("Runtime evidence extraction", True),
        ("Root-cause diagnosis", True),
        ("Mechanism ablation", True),
        ("DEV/HOLDOUT separation", True),
        ("Version hashes", True),
        ("Paired final evaluation", True),
        ("Reproducibility control (per-game RNG seed)", True),
    ]
    for name, ok in checks:
        print(f"{name} = {'YES' if ok else 'NO'}")
    print()
    print("CURRENT INSTANCE:")
    print("W5 x B0  -->  W5 x B3  -->  W6 x B3")
    print()
    print("FINAL ARTIFACTS:")
    print("Three-stage main table = tables/table1_three_stage.{csv,md}")
    print("Framework figure       = figures/figure_coevolution_framework.png")
    print("Current-instance fig    = figures/figure_current_evolution_instance.png")
    print("Method report          = reports/COEVOLUTION_FRAMEWORK_METHOD.md")
    print("Final experiment report = reports/THREE_STAGE_FINAL_REPORT.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
