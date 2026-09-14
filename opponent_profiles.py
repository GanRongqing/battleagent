#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""opponent_profiles.py — policy-level Black opponent ladder (B0–B4).

Pure opponent-policy enhancement. Does NOT change any simulator physics
(radar range / hit probability / weapons / max speed / breakthrough line).

White side is untouched. Black enhancement comes ONLY from:
  - initial waypoint generation (B1 multi-axis, B2 coordinated), and
  - a runtime legal controller (B3 adaptive) that reads Black's OWN radar intel.

Fair-play rules enforced here:
  - Black uses ONLY its own legal observation: get_black_targets() (Black radar intel)
    plus its own unit states. It NEVER reads White-side internal state (tracks,
    allocation, intent, doctrine) — those live in the White process, not the engine.
  - All path/plan functions are PURE functions of (seed, geometry, legal observation):
    identical legal observation ⇒ identical Black action (hidden White truth irrelevant).
  - Variable-cardinality: no per-cardinality count branches. Group count is derived from
    normalized geometry (SHIPS_PER_GROUP capacity) so 3/10/20/30/50 all work.
"""

import math
import random

# ── profiles ──
B0 = "B0_RANDOM"
B1 = "B1_MULTI_AXIS"
B2 = "B2_COORDINATED_PRESSURE"
B3 = "B3_ADAPTIVE"
B4 = "B4_DOCTRINE_MIX"
PROFILES = (B0, B1, B2, B3, B4)
DOCTRINES = (B1, B2, B3)  # B4 randomly picks one per game (seed-driven)

# ── geometry (matches scenario_builder) ──
ENEMY_X = 260000.0
BREAK_X = 50000.0
Y_MIN, Y_MAX = 80000.0, 620000.0

# ── normalized doctrine parameters (scale-independent, not per-count branches) ──
SHIPS_PER_GROUP = 4.0            # group capacity: K = ceil(n / 4) for n=10→3, 20→5, 30→8
LANE_Y_LO, LANE_Y_HI = 180000.0, 600000.0   # lateral approach corridor (normalized)
LATERAL_SPREAD_FRAC = 0.5       # within-group lateral spread (fraction of lane width)
B3_INTERVAL = 15.0              # adaptive replan interval (sim-s)
B3_THREAT_RADIUS = 60000.0      # detected-White proximity that triggers lane shift
B3_HEADING_CHANGE_DEG = 10.0    # replan only if heading change exceeds this (anti-spam)


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def spatial_groups(ys, capacity=SHIPS_PER_GROUP):
    """Scale-independent spatial grouping: y-sorted chunks of `capacity`.

    n=3 → [3], n=10 → [4,4,2], n=20 → [4]*5, n=30 → [4]*7+[2]. No count branches.
    """
    order = sorted(range(len(ys)), key=lambda i: ys[i])
    cap = max(1, int(capacity))
    return [order[k:k + cap] for k in range(0, len(order), cap)]


def _lane_centers(n_groups, y_lo=LANE_Y_LO, y_hi=LANE_Y_HI):
    return [y_lo + (g + 0.5) / n_groups * (y_hi - y_lo) for g in range(n_groups)]


# ════════════════════════════════════════════════════════════════
# B1 — MULTI-AXIS: spatial groups approach from several lateral directions
# ════════════════════════════════════════════════════════════════
def _multi_axis_paths(seed, ys, enemy_x=ENEMY_X, break_x=BREAK_X):
    rng = random.Random(seed)
    groups = spatial_groups(ys)
    lanes = _lane_centers(len(groups))
    span = enemy_x - break_x
    paths = [None] * len(ys)
    for g, members in enumerate(groups):
        lane_y = lanes[g]
        half = LANE_Y_HI - LANE_Y_LO
        for j, i in enumerate(members):
            # within-group lateral offset (multi-axis within group too)
            off = (j - (len(members) - 1) / 2.0) * (half / len(groups)) * LATERAL_SPREAD_FRAC
            off += rng.uniform(-0.15, 0.15) * (half / len(groups))
            path = [[enemy_x, ys[i]]]
            n_wp = rng.randint(3, 5)
            fracs = sorted(rng.uniform(0.12, 0.95) for _ in range(n_wp))
            y = ys[i]
            for f in fracs:
                x = enemy_x - span * f + rng.uniform(-9000.0, 9000.0)
                x = _clamp(x, break_x + 9000.0, enemy_x - 4000.0)
                target_y = lane_y + off + rng.uniform(-0.2, 0.2) * (half / len(groups))
                y += (target_y - y) * 0.55 + rng.uniform(-12000.0, 12000.0)
                y = _clamp(y, Y_MIN, Y_MAX)
                path.append([x, y])
            xf = _clamp(break_x + rng.uniform(0.0, 15000.0), break_x, enemy_x - 4000.0)
            path.append([xf, _clamp(lane_y + off, Y_MIN, Y_MAX)])
            paths[i] = path
    return paths


# ════════════════════════════════════════════════════════════════
# B2 — COORDINATED PRESSURE: group-synchronized lanes + staggered arrival
# ════════════════════════════════════════════════════════════════
def _coordinated_pressure_paths(seed, ys, enemy_x=ENEMY_X, break_x=BREAK_X):
    rng = random.Random(seed)
    groups = spatial_groups(ys)
    lanes = _lane_centers(len(groups))
    span = enemy_x - break_x
    K = len(groups)
    paths = [None] * len(ys)
    for g, members in enumerate(groups):
        lane_y = lanes[g]
        half = LANE_Y_HI - LANE_Y_LO
        # group-level x-schedule: synchronized within group, staggered across groups
        n_wp = rng.randint(3, 4)
        fracs = sorted(rng.uniform(0.18, 0.95) for _ in range(n_wp))
        stagger = (K - 1 - g) / max(1, K) * 0.35   # later groups push west later (spread arrivals)
        for j, i in enumerate(members):
            off = (j - (len(members) - 1) / 2.0) * (half / len(groups)) * LATERAL_SPREAD_FRAC
            path = [[enemy_x, ys[i]]]
            y = ys[i]
            for f in fracs:
                x = enemy_x - span * (f * (1.0 - stagger)) + rng.uniform(-6000.0, 6000.0)
                x = _clamp(x, break_x + 9000.0, enemy_x - 3000.0)
                target_y = lane_y + off
                y += (target_y - y) * 0.65 + rng.uniform(-8000.0, 8000.0)
                y = _clamp(y, Y_MIN, Y_MAX)
                path.append([x, y])
            xf = _clamp(break_x + rng.uniform(0.0, 12000.0), break_x, enemy_x - 3000.0)
            path.append([xf, _clamp(lane_y + off, Y_MIN, Y_MAX)])
            paths[i] = path
    return paths


# ════════════════════════════════════════════════════════════════
# B4 — doctrine mix (seed-driven choice, recorded evaluator-side, invisible to White)
# ════════════════════════════════════════════════════════════════
def pick_doctrine(seed):
    """Deterministic doctrine pick for a game: B1 / B2 / B3 from seed. Never seen by White."""
    return DOCTRINES[random.Random(seed + 0x5EED).randint(0, len(DOCTRINES) - 1)]


def resolve_profile(profile, seed):
    """B4 → resolved concrete doctrine; otherwise return as-is."""
    if profile == B4:
        return pick_doctrine(seed)
    return profile


# ════════════════════════════════════════════════════════════════
# Initial waypoint generation (pure; used at scenario build)
# ════════════════════════════════════════════════════════════════
def generate_initial_paths(profile, seed, ys, enemy_x=ENEMY_X, break_x=BREAK_X):
    """Return initial Black waypoint paths (list of [x,y] chains), one per ship.

    Pure function of (profile, seed, ys, geometry) — no White truth involved.
    B0 is handled by scenario_builder's existing generator; this covers B1/B2/B3/B4.
    """
    resolved = resolve_profile(profile, seed)
    if resolved == B1:
        return _multi_axis_paths(seed, ys, enemy_x, break_x)
    if resolved in (B2, B3):
        return _coordinated_pressure_paths(seed, ys, enemy_x, break_x)
    raise ValueError(f"opponent profile {profile!r} has no initial-path generator "
                     "(B0 handled by scenario_builder; B4 resolved to a doctrine)")


# ════════════════════════════════════════════════════════════════
# B3 — ADAPTIVE: runtime legal replanning from Black's own radar intel
# ════════════════════════════════════════════════════════════════
def observe_black(engine):
    """Build Black's legal observation.

    - black_ships   : Black (BLUE Ship) own states (position, alive)
    - detected_white: only White ships in Black radar intel (get_black_targets)
    Returns a dict. Contains NO White hidden state / internal tracks.
    """
    detected = {}
    try:
        for name in engine.get_black_targets():
            u = engine.unit_by_name(name)
            if u is not None:
                detected[name] = list(u.coords)
    except Exception:
        pass
    black_ships = []
    for u in engine.units():
        if getattr(u, "group", "") == "BLUE":
            black_ships.append({"name": u.name, "position": list(u.coords),
                                "alive": bool(getattr(u, "isactive", True))})
    return {"black_ships": black_ships, "detected_white": detected}


def b3_plan(obs, params=None):
    """Pure adaptive decision. Returns {"replan": {ship_name: [[x,y],[x,y]]}}.

    Only reads obs["black_ships"] and obs["detected_white"] (Black's legal intel).
    Identical legal observation ⇒ identical output (hidden White truth irrelevant).

    Behavior:
      - group Black ships spatially (normalized capacity)
      - default: each group's lane target toward break line
      - if a detected White ship is within threat_radius of the group centroid,
        shift the group lane laterally AWAY from it (legal evasion/dispersion)
    """
    p = params or {}
    threat_r = p.get("threat_radius", B3_THREAT_RADIUS)
    capacity = p.get("ships_per_group", SHIPS_PER_GROUP)
    lane_lo = p.get("lane_y_lo", LANE_Y_LO)
    lane_hi = p.get("lane_y_hi", LANE_Y_HI)
    ships = [s for s in obs.get("black_ships", []) if s.get("alive") and s.get("position")]
    if not ships:
        return {"replan": {}}
    ys = [s["position"][1] for s in ships]
    groups = spatial_groups(ys, capacity)
    lanes = _lane_centers(len(groups), lane_lo, lane_hi)
    detected = [tuple(v) for v in obs.get("detected_white", {}).values()]

    replan = {}
    for g, members in enumerate(groups):
        centroid = (sum(ships[i]["position"][0] for i in members) / len(members),
                    sum(ships[i]["position"][1] for i in members) / len(members))
        # nearest detected White (Black's own intel) to the group centroid
        near = None
        for pos in detected:
            d = math.hypot(pos[0] - centroid[0], pos[1] - centroid[1])
            if near is None or d < near[0]:
                near = (d, pos)
        lane_y = lanes[g]
        push_x = BREAK_X + 12000.0
        if near is not None and near[0] < threat_r:
            # evade laterally: shift lane away from the detected White threat
            dx = near[1][0] - centroid[0]
            dy = near[1][1] - centroid[1]
            dd = math.hypot(dx, dy) or 1.0
            shift = lane_hi - lane_lo
            lane_y += (dy / dd) * shift * 0.35   # perpendicular shift
            lane_y = _clamp(lane_y, lane_lo, lane_hi)
        for j, i in enumerate(members):
            ship = ships[i]
            off = (j - (len(members) - 1) / 2.0) * ((lane_hi - lane_lo) / len(groups)) * LATERAL_SPREAD_FRAC
            target_y = _clamp(lane_y + off, Y_MIN, Y_MAX)
            replan[ship["name"]] = [[ship["position"][0] - 2000.0, ship["position"][1]],
                                    [push_x, target_y]]
    return {"replan": replan}


class B3AdaptiveController:
    """Runtime engine manipulator: re-sails Black ships from legal intel every interval.

    Event counters (replan / lane shift / dispersion / detection) are kept lightweight
    and written to B3_EVENT_LOG (default /tmp/opencode/b3_events.json) whenever a counted
    event occurs — evaluator-side instrumentation, negligible timing impact.
    """

    def __init__(self, seed=None, params=None, interval=B3_INTERVAL):
        self.seed = seed
        self.params = params or {}
        self.interval = interval
        self._last_plan = {}
        self._last_lane = {}
        self.stats = {"calls": 0, "replan_count": 0, "lane_shift_count": 0,
                      "dispersion_event_count": 0, "detected_white_event_count": 0}

    def _write_stats(self, extra=None):
        import os as _os
        path = _os.environ.get("B3_EVENT_LOG", "/tmp/opencode/b3_events.json")
        try:
            import json as _json
            data = dict(self.stats)
            if extra:
                data["error"] = str(extra)
            with open(path, "w", encoding="utf-8") as f:
                _json.dump(data, f)
        except Exception:
            pass

    def __call__(self, engine):
        try:
            obs = observe_black(engine)
            self.stats["calls"] += 1
            plan = b3_plan(obs, self.params)
            new = plan.get("replan", {})
            changed = False
            lane_shift = False
            dispersion = False
            if obs.get("detected_white"):
                self.stats["detected_white_event_count"] += 1
            for name, wp in new.items():
                old = self._last_plan.get(name)
                if old and _heading_change(old, wp) < B3_HEADING_CHANGE_DEG:
                    continue  # no significant change → don't spam sail commands
                ship = engine.get_unit(name)
                if ship is None or not getattr(ship, "isactive", True):
                    continue
                try:
                    engine.cmd_sail_area(name, speed=10, xy_points=wp)
                    self._last_plan[name] = wp
                    self.stats["replan_count"] += 1
                    changed = True
                    lane_y = wp[-1][1]
                    if name in self._last_lane and abs(lane_y - self._last_lane[name]) > 15000.0:
                        lane_shift = True
                    if name in self._last_lane and abs(lane_y - self._last_lane[name]) > 30000.0:
                        dispersion = True
                    self._last_lane[name] = lane_y
                except Exception as e:
                    self._write_stats({"exception": f"sail:{name}:{e}"})
            if lane_shift:
                self.stats["lane_shift_count"] += 1
            if dispersion:
                self.stats["dispersion_event_count"] += 1
            self._write_stats()
        except Exception as e:
            self._write_stats({"exception": f"call:{e}"})


def _heading_change(wp_a, wp_b):
    def hd(wp):
        if len(wp) < 2:
            return None
        dx = wp[1][0] - wp[0][0]
        dy = wp[1][1] - wp[0][1]
        if dx * dx + dy * dy < 1e-6:
            return None
        return math.degrees(math.atan2(dx, dy)) % 360.0
    ha, hb = hd(wp_a), hd(wp_b)
    if ha is None or hb is None:
        return 0.0
    d = abs((ha - hb + 180.0) % 360.0 - 180.0)
    return d
