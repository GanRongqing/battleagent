#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_sync_lock.py — unit tests for C7 (agent_hybrid_sync_lock.py). Target 14/14."""
import math
import sys

import agent_hybrid_v5 as v5
from agent_hybrid_v5 import USV_SPEED
import agent_hybrid_sync_lock as C7
from agent_hybrid_sync_lock import SyncLockController, SYNC_RADIUS, TTFL_GAP_SLOW

# --- isolate from ACE/base allocation: stub the base USVController.step ---
def _stub_step(self, obs, tracks, legal, alloc_result, events, intent=None, mission=None):
    return [(f"{u['name']} 移动 target_speed={USV_SPEED:.1f} target_course=90.0", "move")
            for u in obs.usvs if u.get("is_alive")]
v5.USVController.step = _stub_step


class Track:
    def __init__(self, name, pos, visible=True, has_pos=True, ship=True):
        self.name = name
        self._pos = pos
        self._visible = visible
        self.has_position = has_pos
        self.is_ship = ship
        self.assigned_usvs = set()

    def is_visible(self, now):
        return self._visible

    def predicted_position(self, now):
        return self._pos


class Obs:
    def __init__(self, now, usvs):
        self.now = now
        self.usvs = usvs


def usv(name, pos, alive=True, locking=False, lu=None, frozen=False):
    return {"name": name, "is_alive": alive, "position": pos, "is_locking": locking,
            "locking_unit": lu, "is_frozen": frozen}


class Legal:
    def can_lock(self, u, t):
        return True


def mk(usvs, targets, states, tracks, now=0.0):
    c = SyncLockController()
    for u in usvs:
        c.targets[u["name"]] = targets.get(u["name"])
        c.state[u["name"]] = states.get(u["name"], c.INTERCEPTING)
    return c, Obs(now, usvs), tracks


def test_1_all_engaged_is_noop():
    usvs = [usv("u1", (100000, 0), locking=True, lu="t1"), usv("u2", (101000, 0), locking=True, lu="t1")]
    tracks = {"t1": Track("t1", (90000, 0))}
    c, obs, tr = mk(usvs, {u["name"]: "t1" for u in usvs},
                    {u["name"]: c_LOCKING() for u in usvs}, tracks)
    c.step(obs, tr, Legal(), {}, [], None, "NORMAL")
    assert not c._pkg and not c.package_events


def c_LOCKING():
    return SyncLockController.LOCKING


def test_2_single_owner_no_lock_forms_2unit_package():
    usvs = [usv("u1", (100000, 0)), usv("u2", (110000, 0))]
    tracks = {"t1": Track("t1", (70000, 0))}
    c, obs, tr = mk(usvs, {"u1": "t1", "u2": None}, {"u1": SyncLockController.INTERCEPTING}, tracks)
    c.step(obs, tr, Legal(), {}, [], None, "NORMAL")
    assert c.targets["u2"] == "t1", c.targets
    assert any(e[0] == "FORM" for e in c.package_events), c.package_events
    assert c.package_events[0][1:] == ("t1", "u1", "u2"), c.package_events


def test_3_support_unavailable_no_package():
    usvs = [usv("u1", (100000, 0)), usv("u2", (100000 + SYNC_RADIUS + 5000, 0))]
    tracks = {"t1": Track("t1", (70000, 0))}
    c, obs, tr = mk(usvs, {"u1": "t1", "u2": None}, {"u1": SyncLockController.INTERCEPTING}, tracks)
    c.step(obs, tr, Legal(), {}, [], None, "NORMAL")
    assert not c._pkg, c._pkg


def test_4_stealing_owner_forbidden():
    # u2 owns another target -> not free -> must not be diverted; no package
    usvs = [usv("u1", (100000, 0)), usv("u2", (110000, 0))]
    tracks = {"t1": Track("t1", (70000, 0)), "t2": Track("t2", (160000, 0))}
    c, obs, tr = mk(usvs, {"u1": "t1", "u2": "t2"},
                    {"u1": SyncLockController.INTERCEPTING, "u2": SyncLockController.INTERCEPTING}, tracks)
    c.step(obs, tr, Legal(), {}, [], None, "NORMAL")
    assert "t1" not in c._pkg, c._pkg
    assert c.targets["u2"] == "t2"


def test_5_deterministic_selection_lowest_id_on_tie():
    usvs = [usv("u1", (100000, 0)), usv("uB", (110000, 0)), usv("uA", (110000, 0))]
    tracks = {"t1": Track("t1", (70000, 0))}
    c, obs, tr = mk(usvs, {"u1": "t1", "uB": None, "uA": None},
                    {"u1": SyncLockController.INTERCEPTING}, tracks)
    c.step(obs, tr, Legal(), {}, [], None, "NORMAL")
    assert c._pkg["t1"]["support"] == "uA", c._pkg


def test_6_lead_too_far_ahead_gets_shaped():
    # lead much closer to target than support -> TTFL gap > threshold -> lead action slowed
    usvs = [usv("u1", (72000, 0)), usv("u2", (100000, 0))]
    tracks = {"t1": Track("t1", (70000, 0))}
    c, obs, tr = mk(usvs, {"u1": "t1", "u2": None}, {"u1": SyncLockController.INTERCEPTING}, tracks)
    acts = c.step(obs, tr, Legal(), {}, [], None, "NORMAL")
    lead_acts = [a for a in acts if a[0].startswith("u1 ")]
    assert lead_acts and float(lead_acts[0][0].split("target_speed=")[1].split()[0]) < USV_SPEED, lead_acts


def test_7_support_catches_up_no_shape():
    usvs = [usv("u1", (72000, 0)), usv("u2", (72100, 0))]
    tracks = {"t1": Track("t1", (70000, 0))}
    c, obs, tr = mk(usvs, {"u1": "t1", "u2": None}, {"u1": SyncLockController.INTERCEPTING}, tracks)
    acts = c.step(obs, tr, Legal(), {}, [], None, "NORMAL")
    lead_acts = [a for a in acts if a[0].startswith("u1 ")]
    assert not lead_acts or abs(float(lead_acts[0][0].split("target_speed=")[1].split()[0]) - USV_SPEED) < 1e-6


def test_8_own_lock_established_dissolves():
    usvs = [usv("u1", (72000, 0)), usv("u2", (74000, 0))]
    tracks = {"t1": Track("t1", (70000, 0))}
    c, obs, tr = mk(usvs, {"u1": "t1", "u2": None}, {"u1": SyncLockController.INTERCEPTING}, tracks)
    c.step(obs, tr, Legal(), {}, [], None, "NORMAL")
    assert "t1" in c._pkg
    c.state["u1"] = SyncLockController.LOCKING
    c.step(obs, tr, Legal(), {}, [], None, "NORMAL")
    assert "t1" not in c._pkg


def test_9_target_disappears_dissolves():
    usvs = [usv("u1", (72000, 0)), usv("u2", (74000, 0))]
    tracks = {"t1": Track("t1", (70000, 0))}
    c, obs, tr = mk(usvs, {"u1": "t1", "u2": None}, {"u1": SyncLockController.INTERCEPTING}, tracks)
    c.step(obs, tr, Legal(), {}, [], None, "NORMAL")
    tracks.pop("t1")
    c.step(obs, tracks, Legal(), {}, [], None, "NORMAL")
    assert "t1" not in c._pkg


def test_10_track_expires_dissolves():
    usvs = [usv("u1", (72000, 0)), usv("u2", (74000, 0))]
    tracks = {"t1": Track("t1", (70000, 0))}
    c, obs, tr = mk(usvs, {"u1": "t1", "u2": None}, {"u1": SyncLockController.INTERCEPTING}, tracks)
    c.step(obs, tr, Legal(), {}, [], None, "NORMAL")
    c._pkg["t1"]["t0"] = -10_000.0
    c.step(obs, tr, Legal(), {}, [], None, "NORMAL")
    assert "t1" not in c._pkg


def test_11_timeout_dissolves():
    usvs = [usv("u1", (72000, 0)), usv("u2", (74000, 0))]
    tracks = {"t1": Track("t1", (70000, 0))}
    c, obs, tr = mk(usvs, {"u1": "t1", "u2": None}, {"u1": SyncLockController.INTERCEPTING}, tracks)
    c.step(obs, tr, Legal(), {}, [], None, "NORMAL")
    obs.now = C7.MAX_SYNC_TIME + 1.0
    c.step(obs, tr, Legal(), {}, [], None, "NORMAL")
    assert "t1" not in c._pkg


def test_12_no_permanent_passivity_base_actions_preserved():
    usvs = [usv("u1", (100000, 0)), usv("u9", (300000, 0))]
    tracks = {"t1": Track("t1", (70000, 0))}
    c, obs, tr = mk(usvs, {"u1": "t1", "u9": None}, {"u1": SyncLockController.INTERCEPTING}, tracks)
    acts = c.step(obs, tr, Legal(), {}, [], None, "NORMAL")
    assert any(a[0].startswith("u9 ") for a in acts), acts   # free unit still acts


def test_12b_lead_never_ordered_to_retreat():
    usvs = [usv("u1", (72000, 0)), usv("u2", (76000, 0))]
    tracks = {"t1": Track("t1", (70000, 0))}
    c, obs, tr = mk(usvs, {"u1": "t1", "u2": None}, {"u1": SyncLockController.INTERCEPTING}, tracks)
    for _ in range(30):
        acts = c.step(obs, tr, Legal(), {}, [], None, "NORMAL")
        for a in acts:
            if a[0].startswith("u1 "):
                assert float(a[0].split("target_speed=")[1].split()[0]) > 0.0


def _code_tokens():
    import ast
    tree = ast.parse(open(C7.__file__).read())
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
            b = node.body
            if b and isinstance(b[0], ast.Expr) and isinstance(b[0].value, ast.Constant) \
                    and isinstance(b[0].value.value, str):
                docs.add(b[0].value.value)
    toks = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            toks.append(node.id)
        elif isinstance(node, ast.Attribute):
            toks.append(node.attr)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value not in docs:
            toks.append(node.value)
    return " ".join(toks).lower()


def test_13_no_truth_access():
    toks = _code_tokens()
    for bad in ("black_usv", "ground_truth", "true_pos", "oracle", "truth", "hidden"):
        assert bad not in toks, bad


def test_14_no_strategy_route_id_logic():
    toks = _code_tokens()
    for bad in ("strategy", "route", "横向编队", "菱形编队"):
        assert bad not in toks, bad


def _all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed, failed = 0, []
    for f in fns:
        try:
            f()
            passed += 1
        except Exception as e:  # noqa
            failed.append((f.__name__, repr(e)))
    print(f"passed={passed}/{len(fns)}")
    for n, e in failed:
        print("FAIL", n, e)
    return passed, len(fns), failed


if __name__ == "__main__":
    p, t, f = _all()
    sys.exit(0 if p == t else 1)
