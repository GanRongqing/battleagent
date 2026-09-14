#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""opponent_auto_profiles.py — AUTO_FEINT_SWITCH (policy black-auto-0001-v1).

PHASED ROLE-ASYMMETRIC FEINT-SWITCH opponent policy. Independent of B0-B3; does
not modify any simulator physics and reads ONLY legal Black observation
(engine.get_black_targets() -> detected White positions, plus Black own states).

Behavior (declared, see AUTO_POLICY_DESIGN.md):
  FEINT           small feint group advances on axis A; main force + reserve hold east.
  OBSERVE_RESPONSE observe detected White near axis A (legal intel).
  SWITCH          on legal response evidence OR bounded timeout: commit main force to axis B.
  MAIN_PUSH       main force concentrated on axis B; reserve committed after main advances.
  DEGRADED        if main force heavily attrited, stop re-planning (keep last orders).

Distinct from B3 by construction: sail commands are issued only on a few discrete
phase transitions (low continuous replanning), not every interval.
"""
import math
import random

AUTO = "AUTO_FEINT_SWITCH"
DISPLAY_NAME = "FEINT_SWITCH_V1"

# geometry (matches scenario_builder / opponent_profiles)
ENEMY_X = 260000.0
BREAK_X = 50000.0
Y_MIN, Y_MAX = 80000.0, 620000.0

# role allocation (scale-agnostic fractions, bounded)
FEINT_FRAC = 0.20
RESERVE_FRAC = 0.15
MIN_FEINT = 1

# phase cadence / triggers (sim-seconds / metres)
OBSERVE_INTERVAL = 30.0          # manipulator cadence
FEINT_TIMEOUT = 7000.0           # bounded fallback if no legal response observed
RESPONSE_RADIUS = 60000.0        # detected White near feint axis counts as response
RESPONSE_MIN_WHITE = 2           # legal response evidence threshold
COMMIT_X = 180000.0              # main force x at which reserve is committed
DEGRADE_FRACTION = 0.34

PHASES = ("FEINT", "OBSERVE_RESPONSE", "SWITCH", "MAIN_PUSH", "DEGRADED")


def allocate_roles(n):
    """Scale-agnostic role split. Returns {feint:[idx], main:[idx], reserve:[idx]}.

    n=3 -> feint1 main2 reserve0; n=10 -> 2/7/1; n=20 -> 4/13/3; n=30 -> 6/19/5;
    n=50 -> 10/32/8. Reserve only when n>=5. Never per-count branches.
    """
    idx = list(range(n))
    if n <= 0:
        return {"feint": [], "main": [], "reserve": []}
    nf = max(MIN_FEINT, int(round(n * FEINT_FRAC)))
    nr = int(round(n * RESERVE_FRAC)) if n >= 5 else 0
    if nf + nr > n - 1:
        nr = max(0, n - 1 - nf)
    nf = min(nf, max(1, n - 1))
    nm = n - nf - nr
    if nm < 1:
        nf = max(1, n - nr - 1)
        nm = n - nf - nr
    return {"feint": idx[:nf], "main": idx[nf:nf + nm], "reserve": idx[nf + nm:]}


def _lane_centers(n_groups, y_lo=180000.0, y_hi=600000.0):
    return [y_lo + (g + 0.5) / n_groups * (y_hi - y_lo) for g in range(n_groups)]


def choose_axes(seed, n_groups=3):
    """Deterministic legal axis choice: feint = one lateral extreme, main = the other."""
    rng = random.Random(seed + 0xA17)
    lanes = _lane_centers(n_groups)
    low_first = rng.random() < 0.5
    feint_y = lanes[0] if low_first else lanes[-1]
    main_y = lanes[-1] if low_first else lanes[0]
    return feint_y, main_y


def generate_initial_paths_auto(seed, ys, n_groups=3):
    """Initial Black waypoint paths for FEINT_SWITCH.

    Returns (paths, meta). Feint group advances on axis A; main force and reserve
    hold near the east edge (delayed commitment). Pure function of (seed, ys).
    """
    rng = random.Random(seed)
    n = len(ys)
    roles = allocate_roles(n)
    feint_y, main_y = choose_axes(seed, n_groups)
    span = ENEMY_X - BREAK_X
    paths = [None] * n
    # feint group: advance along feint axis with light jitter
    for k, i in enumerate(roles["feint"]):
        off = (k - (len(roles["feint"]) - 1) / 2.0) * 12000.0
        path = [[ENEMY_X, ys[i]]]
        nwp = rng.randint(3, 5)
        for f in sorted(rng.uniform(0.15, 0.9) for _ in range(nwp)):
            x = ENEMY_X - span * f + rng.uniform(-6000.0, 6000.0)
            x = max(BREAK_X + 12000.0, min(ENEMY_X - 3000.0, x))
            y = feint_y + off + rng.uniform(-8000.0, 8000.0)
            y = max(Y_MIN, min(Y_MAX, y))
            path.append([x, y])
        path.append([BREAK_X + rng.uniform(0.0, 12000.0), max(Y_MIN, min(Y_MAX, feint_y + off))])
        paths[i] = path
    # main force + reserve: HOLD near east (delayed commitment)
    for group in ("main", "reserve"):
        for i in roles[group]:
            paths[i] = [[ENEMY_X, ys[i]], [ENEMY_X - 2500.0, ys[i]]]
    meta = {"roles": roles, "feint_y": feint_y, "main_y": main_y,
            "n": n, "seed": seed, "n_groups": n_groups}
    return paths, meta


def observe_black(engine):
    """Legal Black observation (own ships + detected White intel). No hidden truth."""
    detected = {}
    try:
        for name in engine.get_black_targets():
            u = engine.unit_by_name(name)
            if u is not None:
                detected[name] = list(u.coords)
    except Exception:
        pass
    ships = []
    for u in engine.units():
        if getattr(u, "group", "") == "BLUE":
            ships.append({"name": u.name, "position": list(u.coords),
                          "alive": bool(getattr(u, "isactive", True))})
    return {"black_ships": ships, "detected_white": detected}


def response_triggered(detected_white, feint_y, radius=RESPONSE_RADIUS,
                       min_count=RESPONSE_MIN_WHITE):
    """Legal trigger: enough detected White near the feint axis."""
    near = 0
    for pos in detected_white.values():
        try:
            if abs(float(pos[1]) - feint_y) < radius:
                near += 1
        except Exception:
            continue
    return near >= min_count, near


def _hold_plan(ship):
    return [[ship["position"][0], ship["position"][1]],
            [max(BREAK_X, ship["position"][0] - 2500.0), ship["position"][1]]]


def _main_push_plan(ship, main_y, offset, k, ktot):
    y = max(Y_MIN, min(Y_MAX, main_y + offset))
    return [[ship["position"][0] - 2000.0, ship["position"][1]],
            [BREAK_X + 14000.0, y]]


class FeintSwitchController:
    """Runtime phase state machine (legal observation only). Emits offline events.

    Event counters are written to AUTO_EVENT_LOG (default /tmp/opencode/auto_events.json);
    they are evaluator-side instrumentation and do not affect decisions.
    """

    def __init__(self, seed=None, meta=None, interval=OBSERVE_INTERVAL):
        self.seed = seed
        self.meta = meta or {}
        self.interval = interval
        self.roles = self.meta.get("roles") or {}
        self.feint_y = self.meta.get("feint_y", 400000.0)
        self.main_y = self.meta.get("main_y", 250000.0)
        self.phase = "FEINT"
        self._t = 0.0
        self._main_committed = False
        self._reserve_committed = False
        self._detected_seen = False
        self.stats = {"calls": 0, "phase_switch_count": 0, "replan_count": 0,
                      "feint_phase_entries": 1, "response_trigger_fired": 0,
                      "timeout_switch_fired": 0, "switch_count": 0,
                      "main_push_fired": 0, "reserve_commit_fired": 0,
                      "degraded_count": 0, "detected_white_events": 0,
                      "near_feint_peak": 0, "main_commit_time": None}

    # ---- pure decision step (testable without engine) ----
    def step(self, obs, t):
        """Advance state; return {ship_name: waypoints} for ships to (re)sail now."""
        ships = {s["name"]: s for s in obs.get("black_ships", []) if s.get("alive")}
        detected = obs.get("detected_white", {})
        out = {}
        if detected:
            self._detected_seen = True
            self.stats["detected_white_events"] += 1
        resp, near = response_triggered(detected, self.feint_y)
        self.stats["near_feint_peak"] = max(self.stats["near_feint_peak"], near)

        alive_feint = [ships[self._name(i)] for i in self.roles.get("feint", [])
                       if self._name(i) in ships]
        alive_main = [ships[self._name(i)] for i in self.roles.get("main", [])
                      if self._name(i) in ships]
        feint_frac = (len(alive_feint) / max(1, len(self.roles.get("feint", []))))
        main_frac = (len(alive_main) / max(1, len(self.roles.get("main", []))))

        if self.phase in ("FEINT", "OBSERVE_RESPONSE"):
            if resp:
                self.stats["response_trigger_fired"] = 1
                self._switch("RESPONSE_TRIGGER", t)
            elif t >= FEINT_TIMEOUT:
                self.stats["timeout_switch_fired"] = 1
                self._switch("TIMEOUT", t)
            elif feint_frac < DEGRADE_FRACTION and self.roles.get("feint"):
                self._switch("FEINT_ATTRITION", t)

        if self.phase == "SWITCH":
            # commit main force to axis B (one discrete event)
            out.update(self._commit_main(ships))
            self.phase = "MAIN_PUSH"
            self.stats["main_push_fired"] = 1

        if self.phase == "MAIN_PUSH":
            # commit reserve once main force has advanced far enough west
            if not self._reserve_committed and alive_main:
                cx = sum(s["position"][0] for s in alive_main) / len(alive_main)
                if cx <= COMMIT_X:
                    out.update(self._commit_reserve(ships))
            if main_frac < DEGRADE_FRACTION:
                self.phase = "DEGRADED"
                self.stats["degraded_count"] += 1

        if self.phase == "DEGRADED":
            pass  # keep last orders; no continuous re-planning
        return out

    def _name(self, i):
        names = self.meta.get("names")
        if names and i < len(names):
            return names[i]
        return f"black_usv{i + 1}"

    def _switch(self, reason, t):
        self.phase = "SWITCH"
        self.stats["phase_switch_count"] += 1
        self.stats["switch_count"] += 1
        self.stats["main_commit_time"] = round(t, 1)
        self._switch_reason = reason

    def _commit_main(self, ships):
        out = {}
        ids = self.roles.get("main", [])
        for k, i in enumerate(ids):
            nm = self._name(i)
            if nm in ships:
                off = (k - (len(ids) - 1) / 2.0) * 11000.0
                out[nm] = _main_push_plan(ships[nm], self.main_y, off, k, len(ids))
        self._main_committed = True
        return out

    def _commit_reserve(self, ships):
        out = {}
        ids = self.roles.get("reserve", [])
        for k, i in enumerate(ids):
            nm = self._name(i)
            if nm in ships:
                off = (k - (len(ids) - 1) / 2.0) * 9000.0
                out[nm] = _main_push_plan(ships[nm], self.main_y, off, k, len(ids))
        self._reserve_committed = True
        self.stats["reserve_commit_fired"] = 1
        self.stats["phase_switch_count"] += 1
        return out

    def _write_stats(self):
        import os
        import json
        path = os.environ.get("AUTO_EVENT_LOG", "/tmp/opencode/auto_events.json")
        try:
            data = dict(self.stats)
            data["phase"] = self.phase
            data["roles"] = {k: len(v) for k, v in self.roles.items()}
            data["feint_y"] = self.feint_y
            data["main_y"] = self.main_y
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception:
            pass

    def __call__(self, engine):
        try:
            obs = observe_black(engine)
            self.stats["calls"] += 1
            self._t += self.interval
            plan = self.step(obs, self._t)
            for nm, wp in plan.items():
                u = engine.get_unit(nm)
                if u is None or not getattr(u, "isactive", True):
                    continue
                try:
                    engine.cmd_sail_area(nm, speed=10, xy_points=wp)
                    self.stats["replan_count"] += 1
                except Exception:
                    pass
            self._write_stats()
        except Exception as e:
            try:
                self.stats["error"] = str(e)
                self._write_stats()
            except Exception:
                pass
