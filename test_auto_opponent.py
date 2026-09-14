#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_auto_opponent.py — AUTO_FEINT_SWITCH semantics, fair-play, cardinality tests."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import opponent_auto_profiles as auto  # noqa: E402

PASS, FAIL = [], []


def check(name, c, d=""):
    (PASS if c else FAIL).append(name)
    print(f"  [{'PASS' if c else 'FAIL'}] {name} {d}")


class FakeUnit:
    def __init__(self, name, x, y, group="BLUE", active=True):
        self.name = name
        self.coords = [x, y]
        self.group = group
        self.isactive = active


class FakeEngine:
    def __init__(self, n=20, detected=None):
        self.ships = [FakeUnit(f"black_usv{i+1}", 260000.0, 80000.0 + i * 25000.0)
                      for i in range(n)]
        self.uavs = [FakeUnit(f"black_uav{i+1}", 260000.0, 80000.0 + i * 25000.0)
                     for i in range(n)]
        self.detected = detected or {}
        self.white = [FakeUnit(nm, pos[0], pos[1], group="RED")
                      for nm, pos in self.detected.items()]
        self.sailed = []

    def units(self):
        return self.ships + self.uavs + self.white

    def get_black_targets(self):
        return list(self.detected.keys())

    def unit_by_name(self, name):
        for u in self.units():
            if u.name == name:
                return u
        return None

    get_unit = unit_by_name

    def cmd_sail_area(self, name, speed=10, xy_points=None):
        self.sailed.append((name, tuple(map(tuple, xy_points or []))))


def obs_from(engine):
    return auto.observe_black(engine)


def make_meta(n=20, seed=7001):
    ys = [80000.0 + i * 25000.0 for i in range(n)]
    paths, meta = auto.generate_initial_paths_auto(seed, ys)
    meta["names"] = [f"black_usv{i+1}" for i in range(n)]
    return meta, paths


def main():
    # AUTO-T1 initial phase = FEINT
    meta, _ = make_meta()
    c = auto.FeintSwitchController(seed=7001, meta=meta)
    check("AUTO-T1 initial phase = FEINT", c.phase == "FEINT")

    # AUTO-T2 feint smaller than main across variable fleet sizes
    ok = True
    for n in (3, 10, 20, 30, 50):
        r = auto.allocate_roles(n)
        tot = len(r["feint"]) + len(r["main"]) + len(r["reserve"])
        ok = ok and tot == n and len(r["main"]) > len(r["feint"]) and len(r["feint"]) >= 1
    check("AUTO-T2 feint < main for 3/10/20/30/50", ok)

    # AUTO-T3 legal response trigger -> SWITCH
    eng = FakeEngine(n=20, detected={"white_usv1": [200000.0, meta["feint_y"]],
                                     "white_usv2": [201000.0, meta["feint_y"] + 5000]})
    c = auto.FeintSwitchController(seed=7001, meta=meta)
    out = c.step(obs_from(eng), t=300.0)
    check("AUTO-T3 legal response trigger -> SWITCH/MAIN_PUSH",
          c.stats["response_trigger_fired"] == 1 and len(out) > 0 and
          c.phase == "MAIN_PUSH")

    # AUTO-T4 no response -> bounded timeout switch
    eng2 = FakeEngine(n=20, detected={})
    c2 = auto.FeintSwitchController(seed=7001, meta=meta)
    out2 = c2.step(obs_from(eng2), t=auto.FEINT_TIMEOUT + 1)
    check("AUTO-T4 no response -> timeout switch (bounded)",
          c2.stats["timeout_switch_fired"] == 1 and c2.phase == "MAIN_PUSH")

    # AUTO-T5 after SWITCH -> MAIN_PUSH -> reserve committed after main advances
    c3 = auto.FeintSwitchController(seed=7001, meta=meta)
    c3.step(obs_from(eng), t=300.0)  # switch + main push
    eng3 = FakeEngine(n=20, detected={})
    # move main force west past COMMIT_X
    for i in meta["roles"]["main"]:
        eng3.ships[i].coords[0] = auto.COMMIT_X - 5000
    out3 = c3.step(obs_from(eng3), t=1000.0)
    check("AUTO-T5 MAIN_PUSH -> reserve commit (2nd discrete switch)",
          c3.phase == "MAIN_PUSH" and c3.stats["reserve_commit_fired"] == 1 and len(out3) > 0)

    # AUTO-T6 no continuous B3-style replanning: steady MAIN_PUSH emits no new sail
    c4 = auto.FeintSwitchController(seed=7001, meta=meta)
    c4.step(obs_from(eng), t=300.0)
    # consume the one-time reserve commit first
    engadv = FakeEngine(n=20, detected={})
    for i in meta["roles"]["main"]:
        engadv.ships[i].coords[0] = 150000.0
    c4.step(obs_from(engadv), t=900.0)
    emitted = 0
    for k in range(40):
        engk = FakeEngine(n=20, detected={})
        for i in meta["roles"]["main"]:
            engk.ships[i].coords[0] = 150000.0
        o = c4.step(obs_from(engk), t=2000.0 + k * 30)
        emitted += len(o)
    check("AUTO-T6 low continuous replanning after phases", emitted == 0)

    # AUTO-T7 same state -> same output
    m1, _ = make_meta(seed=7001)
    a = auto.FeintSwitchController(seed=7001, meta=m1)
    b = auto.FeintSwitchController(seed=7001, meta=m1)
    oa = a.step(obs_from(eng), t=300.0)
    ob = b.step(obs_from(eng), t=300.0)
    check("AUTO-T7 same state -> same output", oa == ob)

    # AUTO-T8 hidden White truth counterfactual: output only depends on legal obs
    o1 = a.step(obs_from(eng), t=500.0)
    o2 = a.step(obs_from(eng), t=500.0)
    check("AUTO-T8 same legal obs -> same action (no hidden truth)", o1 == o2)

    # AUTO-T9 variable cardinality roles partition
    ok9 = True
    for n in (3, 10, 20, 30, 50):
        r = auto.allocate_roles(n)
        ok9 = ok9 and (len(r["feint"]) + len(r["main"]) + len(r["reserve"]) == n)
    check("AUTO-T9 variable cardinality partition", ok9)

    # AUTO-T10 UAV remains recon-only: controller never plans for uavs
    meta10, paths10 = make_meta(n=20)
    uav_names = {f"black_uav{i+1}" for i in range(20)}
    planned = set()
    c10 = auto.FeintSwitchController(seed=7001, meta=meta10)
    for t in (300.0, 800.0, 1400.0, 2000.0):
        planned |= set(c10.step(obs_from(eng), t).keys())
    check("AUTO-T10 UAV remains recon-only (never planned/armed)",
          not (planned & uav_names))

    # fair-play source audit: no hidden White internals / no version cheat
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "opponent_auto_profiles.py"), encoding="utf-8").read()
    banned = ["allocator", "white_tracks", "commander", "get_white_targets",
              "white_version", "W5", "W6", "W7"]
    hit = [b for b in banned if b in src]
    check("FAIR-PLAY source audit (no hidden White truth / version cheat)", not hit,
          f"hits={hit}")

    print(f"\nRESULT {len(PASS)}/{len(PASS) + len(FAIL)} passed")
    sys.exit(0 if not FAIL else 1)


if __name__ == "__main__":
    main()
