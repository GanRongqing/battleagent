#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_anti_leak.py — white-auto-0001-v1 containment tests (WC-T1..T10 + fair-play
+ W5-equivalence outside trigger).

Note: W5's allocator has a coverage floor that assigns >=1 USV to every ship, so
containment is tested as the DELTA over W5 (extra blocker), not mere presence.
Each call gets a fresh tracks dict (tracks mutate assigned_usvs).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agent_hybrid_v5 as w5  # noqa: E402
import agent_hybrid_w8_containment as w8  # noqa: E402

PASS, FAIL = [], []


def check(name, c, d=""):
    (PASS if c else FAIL).append(name)
    print(f"  [{'PASS' if c else 'FAIL'}] {name} {d}")


def mk_track(name, x, y, vx, vy, now=0.0, conf=1.0):
    t = w5.EnemyTrack(name, now)
    t.has_position = True
    t.last_position = (x, y)
    t.last_velocity = (vx, vy)
    t.last_seen_time = now
    t.point_confidence = conf
    return t


def fresh_tracks(specs):
    return {nm: mk_track(*spec) for nm, spec in specs.items()}


def mk_usvs(n, x=200000.0):
    return [{"name": f"white_usv{i+1}", "position": [x - i * 1000.0, 300000.0], "is_alive": True}
            for i in range(n)]


def main():
    # WC-T1 moving away -> no containment trigger
    a = w8.ContainmentAllocator()
    tr = fresh_tracks({"E1": ("black_usv1", 100000.0, 300000.0, +10.0, 0.0)})
    usvs = mk_usvs(3)
    a.allocate_usvs(tr, usvs, {u["name"]: None for u in usvs}, 0.0)
    check("WC-T1 target moving away -> no containment", a.stats["containment_triggered"] == 0)

    # WC-T2 toward boundary but existing effective blocker -> no new assignment
    a = w8.ContainmentAllocator()
    tr = fresh_tracks({"E1": ("black_usv1", 100000.0, 300000.0, -10.0, 0.0)})
    usvs = [{"name": "white_usv1", "position": [80000.0, 300000.0], "is_alive": True}]
    res = a.allocate_usvs(tr, usvs, {"white_usv1": "E1"}, 0.0)
    check("WC-T2 existing effective blocker -> no new containment",
          a.stats["containment_triggered"] == 0)

    # WC-T3 HIGH risk, no blocker, FREE USV -> exactly one extra blocker
    a = w8.ContainmentAllocator()
    base = w5.ThreatAllocator()
    tr = fresh_tracks({"E1": ("black_usv1", 100000.0, 300000.0, -10.0, 0.0)})  # eta 5000 HIGH
    usvs = mk_usvs(6)
    r0 = base.allocate_usvs(fresh_tracks({"E1": ("black_usv1", 100000.0, 300000.0, -10.0, 0.0)}),
                            usvs, {u["name"]: None for u in usvs}, 0.0)
    res = a.allocate_usvs(tr, usvs, {u["name"]: None for u in usvs}, 0.0)
    check("WC-T3 HIGH + no blocker + FREE -> exactly one extra blocker",
          a.stats["containment_triggered"] == 1 and len(res.get("E1", [])) == len(r0.get("E1", [])) + 1)

    # WC-T4 free unavailable, low-priority owner with 2 -> bounded preemption
    a = w8.ContainmentAllocator()
    tr = fresh_tracks({"E1": ("black_usv1", 100000.0, 300000.0, -10.0, 0.0),
                       "E2": ("black_usv2", 200000.0, 200000.0, -1.0, 0.0)})
    usvs = [{"name": "white_usv1", "position": [150000.0, 200000.0], "is_alive": True},
            {"name": "white_usv2", "position": [160000.0, 200000.0], "is_alive": True}]
    res = a.allocate_usvs(tr, usvs, {"white_usv1": "E2", "white_usv2": "E2"}, 0.0)
    check("WC-T4 no free -> bounded preemption", a.stats["preemptions"] == 1 and
          len(res.get("E1", [])) == 1)

    # WC-T5 CRITICAL -> one extra blocker; no duplicate while blocker present
    a = w8.ContainmentAllocator()
    tr = fresh_tracks({"E1": ("black_usv1", 60000.0, 300000.0, -10.0, 0.0)})  # eta 1000 CRITICAL
    usvs = mk_usvs(3)
    res1 = a.allocate_usvs(tr, usvs, {u["name"]: None for u in usvs}, 0.0)
    blocker = res1.get("E1", [None])[0]
    usvs2 = mk_usvs(3)
    for u in usvs2:
        if u["name"] == blocker:
            u["position"] = [55000.0, 300000.0]
    um2 = {u["name"]: None for u in usvs2}
    um2[blocker] = "E1"
    tr2 = fresh_tracks({"E1": ("black_usv1", 60000.0, 300000.0, -10.0, 0.0)})
    before = a.stats["containment_triggered"]
    res2 = a.allocate_usvs(tr2, usvs2, um2, 100.0)
    check("WC-T5 CRITICAL one blocker; no duplicate while present",
          a.stats["critical_risk_seen"] >= 1 and a.stats["containment_triggered"] == before)

    # WC-T6 hysteresis prevents oscillation
    a = w8.ContainmentAllocator()
    usvs = mk_usvs(6)
    a.allocate_usvs(fresh_tracks({"E1": ("black_usv1", 100000.0, 300000.0, -10.0, 0.0)}),
                    usvs, {u["name"]: None for u in usvs}, 0.0)
    still = "E1" in a._contained
    a.allocate_usvs(fresh_tracks({"E1": ("black_usv1", 100000.0, 300000.0, +10.0, 0.0)}),
                    usvs, {u["name"]: None for u in usvs}, 100.0)
    held = "E1" in a._contained
    a.allocate_usvs(fresh_tracks({"E1": ("black_usv1", 100000.0, 300000.0, +10.0, 0.0)}),
                    usvs, {u["name"]: None for u in usvs}, 1000.0)
    released = "E1" not in a._contained
    check("WC-T6 hysteresis: held before TTL, released after", still and held and released)

    # WC-T7 target killed -> release
    a = w8.ContainmentAllocator()
    usvs = mk_usvs(3)
    a.allocate_usvs(fresh_tracks({"E1": ("black_usv1", 100000.0, 300000.0, -10.0, 0.0)}),
                    usvs, {u["name"]: None for u in usvs}, 0.0)
    w5._KILLED.add("E1")
    a.allocate_usvs(fresh_tracks({"E1": ("black_usv1", 100000.0, 300000.0, -10.0, 0.0)}),
                    usvs, {u["name"]: None for u in usvs}, 100.0)
    w5._KILLED.discard("E1")
    check("WC-T7 target killed -> containment released", "E1" not in a._contained)

    # WC-T8 no crossing risk -> W5 assignment unchanged
    base = w5.ThreatAllocator(); cand = w8.ContainmentAllocator()
    spec = {"E1": ("black_usv1", 200000.0, 300000.0, -1.0, 0.0),
            "E2": ("black_usv2", 210000.0, 320000.0, -1.0, 0.0)}
    usvs = mk_usvs(3)
    r0 = base.allocate_usvs(fresh_tracks(spec), usvs, {u["name"]: None for u in usvs}, 0.0)
    r1 = cand.allocate_usvs(fresh_tracks(spec), usvs, {u["name"]: None for u in usvs}, 0.0)
    check("WC-T8 no risk -> identical to W5", r0 == r1 and cand.stats["containment_triggered"] == 0)

    # WC-T9 hidden-truth counterfactual
    a1 = w8.ContainmentAllocator(); a2 = w8.ContainmentAllocator()
    spec = {"E1": ("black_usv1", 100000.0, 300000.0, -10.0, 0.0)}
    usvs = mk_usvs(3)
    o1 = a1.allocate_usvs(fresh_tracks(spec), usvs, {u["name"]: None for u in usvs}, 0.0)
    o2 = a2.allocate_usvs(fresh_tracks(spec), usvs, {u["name"]: None for u in usvs}, 0.0)
    check("WC-T9 same legal obs -> same action", o1 == o2)

    # WC-T10 variable cardinality
    ok = True
    for n in (5, 10, 15):
        a = w8.ContainmentAllocator()
        usvs = mk_usvs(n)
        a.allocate_usvs(fresh_tracks({"E1": ("black_usv1", 100000.0, 300000.0, -10.0, 0.0)}),
                        usvs, {u["name"]: None for u in usvs}, 0.0)
        ok = ok and a.stats["containment_triggered"] == 1
    check("WC-T10 variable cardinality 5/10/15", ok)

    # W5-equivalence outside trigger over 500 synthetic states
    base = w5.ThreatAllocator(); cand = w8.ContainmentAllocator()
    eq = 0; total = 0
    for i in range(500):
        x = 150000.0 + (i % 50) * 2000.0
        spec = {"E1": ("black_usv1", x, 300000.0, -1.0, 0.0),
                "E2": ("black_usv2", x + 5000, 320000.0, +1.0, 0.0)}
        usvs = mk_usvs(1 + (i % 4))
        um = {u["name"]: None for u in usvs}
        r0 = base.allocate_usvs(fresh_tracks(spec), usvs, dict(um), 0.0)
        r1 = cand.allocate_usvs(fresh_tracks(spec), usvs, dict(um), 0.0)
        total += 1
        eq += 1 if r0 == r1 else 0
    check("W5-equivalence outside trigger (500 states)", eq == total, f"{eq}/{total}")

    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "agent_hybrid_w8_containment.py"), encoding="utf-8").read()
    banned = ["get_white_targets", "ground_truth", "hidden_truth", "if seed =="]
    hit = [b for b in banned if b in src]
    check("fair-play source audit (legal tracks only)", not hit, f"hits={hit}")

    print(f"\nRESULT {len(PASS)}/{len(PASS) + len(FAIL)} passed")
    sys.exit(0 if not FAIL else 1)


if __name__ == "__main__":
    main()
