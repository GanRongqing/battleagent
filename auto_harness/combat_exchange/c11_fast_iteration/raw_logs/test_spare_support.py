#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_spare_support.py — unit tests for C11 (agent_hybrid_spare_support.py)."""
import json
import sys

import agent_hybrid_v5 as v5
from agent_hybrid_v5 import USV_SPEED
import agent_hybrid_spare_support as C11
from agent_hybrid_spare_support import SpareSupportController, SPARE_RANGE, MAX_TOTAL_PACKAGES


def _stub(self, obs, tracks, legal, alloc_result, events, intent=None, mission=None):
    return [(f"{u['name']} 移动 target_speed={USV_SPEED:.1f} target_course=90.0", "move")
            for u in obs.usvs if u.get("is_alive")]
v5.USVController.step = _stub


class Track:
    def __init__(self, name, pos, visible=True, has_pos=True, ship=True):
        self.name = name; self._pos = pos; self._visible = visible
        self.has_position = has_pos; self.is_ship = ship

    def is_visible(self, now): return self._visible
    def predicted_position(self, now): return self._pos


class Obs:
    def __init__(self, now, usvs):
        self.now = now; self.usvs = usvs


def usv(name, pos, alive=True):
    return {"name": name, "is_alive": alive, "position": pos, "is_locked": False,
            "locked_attacker": [], "is_locking": False}


def mk(usvs, targets, states, tracks):
    c = SpareSupportController()
    for u in usvs:
        c.targets[u["name"]] = targets.get(u["name"])
        c.state[u["name"]] = states.get(u["name"], c.INTERCEPTING)
    return c, Obs(0.0, usvs), tracks


def run(c, obs, tr):
    return c.step(obs, tr, {}, {}, [], None, "NORMAL")


def test_1_engaged_support_rejected():
    # u2 is within 40km of a visible track -> must NOT be diverted
    usvs = [usv("u1", (100000, 0)), usv("u2", (110000, 0))]
    tracks = {"t1": Track("t1", (70000, 0)), "tE": Track("tE", (130000, 0))}  # tE near u2 (20km)
    c, obs, tr = mk(usvs, {"u1": "t1", "u2": None}, {"u1": SpareSupportController.INTERCEPTING}, tracks)
    run(c, obs, tr)
    assert "t1" not in c._pkg, c.package_events


def test_2_spare_support_forms():
    usvs = [usv("u1", (100000, 0)), usv("u2", (130000, 0))]
    tracks = {"t1": Track("t1", (70000, 0))}   # u2 far from any track
    c, obs, tr = mk(usvs, {"u1": "t1", "u2": None}, {"u1": SpareSupportController.INTERCEPTING}, tracks)
    run(c, obs, tr)
    assert "t1" in c._pkg and c._pkg["t1"]["support"] == "u2", c.package_events


def test_3_non_trigger_equivalence():
    usvs = [usv("u1", (100000, 0)), usv("u2", (110000, 0))]
    tracks = {"t1": Track("t1", (70000, 0)), "tE": Track("tE", (111000, 0))}
    c, obs, tr = mk(usvs, {"u1": "t1", "u2": None}, {"u1": SpareSupportController.INTERCEPTING}, tracks)
    acts = run(c, obs, tr)
    names = [a[0].split(" ", 1)[0] for a in acts]
    assert "u1" in names and "u2" in names, acts   # no diversion when gate closed


def test_4_budget_still_enforced():
    c = SpareSupportController()
    usvs = [usv("u1", (100000, 0)), usv("u2", (140000, 0)), usv("u3", (141000, 0))]
    tracks = {}
    c.targets = {"u1": "t1", "u2": None, "u3": None}
    c.state = {n: c.INTERCEPTING for n in ("u1", "u2", "u3")}
    for i in range(MAX_TOTAL_PACKAGES + 2):
        tracks[f"t{i}"] = Track(f"t{i}", (70000 + i * 1000, 0))
        c.targets["u1"] = f"t{i}"; c.targets["u2"] = None; c.targets["u3"] = None
        c.state["u1"] = c.INTERCEPTING
        run(c, Obs(float(i), usvs), tracks)
        c._pkg.clear()
    assert c._formed_total == MAX_TOTAL_PACKAGES, c._formed_total


def test_5_deterministic_output():
    usvs = [usv("u1", (100000, 0)), usv("u2", (110000, 0))]
    tracks = {"t1": Track("t1", (70000, 0))}
    a, obs, tr = mk(usvs, {"u1": "t1", "u2": None}, {"u1": SpareSupportController.INTERCEPTING}, tracks)
    r1 = run(a, obs, tr)
    b, obs2, tr2 = mk(usvs, {"u1": "t1", "u2": None}, {"u1": SpareSupportController.INTERCEPTING}, tracks)
    r2 = run(b, obs2, tr2)
    assert r1 == r2


def c_INTERCEPT():
    return SpareSupportController.INTERCEPTING


def test_6_no_truth_no_strategy_id():
    import ast
    tree = ast.parse(open(C11.__file__).read())
    docs = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)):
            b = n.body
            if b and isinstance(b[0], ast.Expr) and isinstance(b[0].value, ast.Constant):
                docs.add(b[0].value.value)
    toks = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Name): toks.append(n.id)
        elif isinstance(n, ast.Attribute): toks.append(n.attr)
        elif isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value not in docs:
            toks.append(n.value)
    blob = " ".join(toks).lower()
    for bad in ("black_usv", "ground_truth", "true_pos", "oracle", "truth", "strategy", "route"):
        assert bad not in blob, bad


def _all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    p = 0
    for f in fns:
        try:
            f(); p += 1
        except Exception as e:
            print("FAIL", f.__name__, repr(e))
    print(f"passed={p}/{len(fns)}")
    return p == len(fns)


if __name__ == "__main__":
    sys.exit(0 if _all() else 1)
