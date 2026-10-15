#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_demand_gate.py — unit tests for C9 (agent_hybrid_demand_gate.py)."""
import json
import sys

import agent_hybrid_v5 as v5
from agent_hybrid_v5 import USV_SPEED
import agent_hybrid_demand_gate as C9
from agent_hybrid_demand_gate import DemandGateController, SYNC_RADIUS


def _stub_step(self, obs, tracks, legal, alloc_result, events, intent=None, mission=None):
    return [(f"{u['name']} 移动 target_speed={USV_SPEED:.1f} target_course=90.0", "move")
            for u in obs.usvs if u.get("is_alive")]
v5.USVController.step = _stub_step


class Track:
    def __init__(self, name, pos, visible=True, has_pos=True, ship=True):
        self.name = name; self._pos = pos; self._visible = visible
        self.has_position = has_pos; self.is_ship = ship

    def is_visible(self, now): return self._visible
    def predicted_position(self, now): return self._pos


class Obs:
    def __init__(self, now, usvs):
        self.now = now; self.usvs = usvs


def usv(name, pos, alive=True, locked=False, attackers=None):
    return {"name": name, "is_alive": alive, "position": pos, "is_locked": locked,
            "locked_attacker": attackers or [], "is_locking": False}


def mk(usvs, targets, states, tracks):
    c = DemandGateController()
    for u in usvs:
        c.targets[u["name"]] = targets.get(u["name"])
        c.state[u["name"]] = states.get(u["name"], c.INTERCEPTING)
    return c, Obs(0.0, usvs), tracks


def test_1_no_hostile_lock_no_package():
    usvs = [usv("u1", (100000, 0)), usv("u2", (110000, 0))]
    tracks = {"t1": Track("t1", (70000, 0))}
    c, obs, tr = mk(usvs, {"u1": "t1", "u2": None}, {"u1": c_INTERCEPT()}, tracks)
    c.step(obs, tr, {}, {}, [], None, "NORMAL")
    assert not c._pkg, c.package_events


def c_INTERCEPT():
    return DemandGateController.INTERCEPTING


def test_2_hostile_lock_forms_package():
    usvs = [usv("u1", (100000, 0), locked=True, attackers=["usv9"]), usv("u2", (110000, 0))]
    tracks = {"t1": Track("t1", (70000, 0))}
    c, obs, tr = mk(usvs, {"u1": "t1", "u2": None}, {"u1": c_INTERCEPT()}, tracks)
    c.step(obs, tr, {}, {}, [], None, "NORMAL")
    assert "t1" in c._pkg and c._pkg["t1"]["support"] == "u2", c.package_events


def test_3_hostile_lock_no_support_no_package():
    usvs = [usv("u1", (100000, 0), locked=True, attackers=["usv9"]),
            usv("u2", (100000 + SYNC_RADIUS + 9000, 0))]
    tracks = {"t1": Track("t1", (70000, 0))}
    c, obs, tr = mk(usvs, {"u1": "t1", "u2": None}, {"u1": c_INTERCEPT()}, tracks)
    c.step(obs, tr, {}, {}, [], None, "NORMAL")
    assert not c._pkg


def test_4_owner_locking_no_package():
    usvs = [usv("u1", (100000, 0), locked=True, attackers=["usv9"]), usv("u2", (110000, 0))]
    tracks = {"t1": Track("t1", (70000, 0))}
    c, obs, tr = mk(usvs, {"u1": "t1", "u2": None}, {"u1": DemandGateController.LOCKING}, tracks)
    c.step(obs, tr, {}, {}, [], None, "NORMAL")
    assert not c._pkg


def test_5_non_trigger_equivalence_base_actions_kept():
    usvs = [usv("u1", (100000, 0)), usv("u2", (110000, 0))]
    tracks = {"t1": Track("t1", (70000, 0))}
    c, obs, tr = mk(usvs, {"u1": "t1", "u2": None}, {"u1": c_INTERCEPT()}, tracks)
    acts = c.step(obs, tr, {}, {}, [], None, "NORMAL")
    # gate not triggered -> every base action preserved unchanged (redirects the owner only)
    names = [a[0].split(" ", 1)[0] for a in acts]
    assert "u1" in names and "u2" in names, acts


def test_6_deterministic_selection():
    usvs = [usv("u1", (100000, 0), locked=True, attackers=["usv9"]),
            usv("uB", (110000, 0)), usv("uA", (110000, 0))]
    tracks = {"t1": Track("t1", (70000, 0))}
    c, obs, tr = mk(usvs, {"u1": "t1", "uB": None, "uA": None}, {"u1": c_INTERCEPT()}, tracks)
    c.step(obs, tr, {}, {}, [], None, "NORMAL")
    assert c._pkg["t1"]["support"] == "uA"


def test_7_dissolve_on_member_lock():
    usvs = [usv("u1", (72000, 0), locked=True, attackers=["usv9"]), usv("u2", (74000, 0))]
    tracks = {"t1": Track("t1", (70000, 0))}
    c, obs, tr = mk(usvs, {"u1": "t1", "u2": None}, {"u1": c_INTERCEPT()}, tracks)
    c.step(obs, tr, {}, {}, [], None, "NORMAL")
    assert "t1" in c._pkg
    c.state["u1"] = DemandGateController.LOCKING
    c.step(obs, tr, {}, {}, [], None, "NORMAL")
    assert "t1" not in c._pkg


def test_8_no_truth_or_strategy_id():
    import ast
    tree = ast.parse(open(C9.__file__).read())
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
