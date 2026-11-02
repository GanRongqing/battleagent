#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""scenario_agnostic_safety.py — E30: ScenarioAgnosticBoundarySafety.

Fixes E29 root cause: the old layer hardcoded the W2 rectangle (y ±277.8 km) and rewrote every scale-scenario
USV (deployed at y≈375–435 km) toward (185,0), destroying the engagement. This layer uses the **real public
operational-area polygon** served by the engine (same polygon the judge uses), obtained legally via /status.
It intervenes ONLY when the predicted next-step position is outside the real polygon (or the unit is already
outside); interior motion is never rewritten. If no valid public area is available it does NOT fall back to a
hardcoded box — it flags the episode safety-unavailable and leaves actions unchanged.
"""
import math
import re

from agent_hybrid_v5 import ActionSafety, bearing_to

try:
    from shapely.geometry import Polygon, Point
except Exception:  # pragma: no cover
    Polygon = None
    Point = None

_SRE = re.compile(r"target_speed=([-\d.]+)")
_CRE = re.compile(r"target_course=([-\d.]+)")
DT = 31.0
BUFFER = 5_000.0   # only triggers near the real boundary when approaching it


class ScenarioAgnosticBoundarySafety(ActionSafety):
    def __init__(self):
        super().__init__()
        self.area_rewrites = 0
        self.predicted_out_rewrites = 0
        self.unnecessary_rewrites = 0
        self.available = False
        self.unavailable_reason = ""

    @staticmethod
    def _predict(x, y, sp, crs, dt=DT):
        r = math.radians(crs)
        return x + sp * dt * math.sin(r), y + sp * dt * math.cos(r)

    def _poly(self, obs):
        pts = getattr(obs, "public_area", None)
        if not pts or len(pts) < 3 or Polygon is None:
            return None
        try:
            p = Polygon([(float(a), float(b)) for a, b in pts])
            if (not p.is_valid) or p.area <= 0.0:
                return None
            return p
        except Exception:
            return None

    def filter(self, actions, obs, legal):
        safe = super().filter(actions, obs, legal)
        poly = self._poly(obs)
        if poly is None:
            self.available = False
            self.unavailable_reason = "no/invalid public_area in observation"
            return safe
        self.available = True
        usv = {u["name"]: u for u in obs.usvs if u.get("is_alive") and u.get("position")}
        uav = {u["name"]: u for u in obs.uavs if u.get("is_alive") and u.get("position")}
        out = []
        for a in safe:
            text = a["action_text"]; atype = a["action_type"]
            unit = text.split(" ", 1)[0] if text else None
            src = None
            if atype == "move" and unit in usv:
                src = usv[unit]["position"]
            elif atype == "fly" and unit in uav:
                src = uav[unit]["position"]
            if src is not None:
                ms = _SRE.search(text); mc = _CRE.search(text)
                if ms and mc:
                    sp = float(ms.group(1)); crs = float(mc.group(1))
                    x, y = float(src[0]), float(src[1])
                    px, py = self._predict(x, y, sp, crs)
                    inside_now = poly.contains(Point(x, y))
                    inside_next = poly.contains(Point(px, py))
                    _near_approach = False
                    if inside_now and inside_next:
                        try:
                            d_now = poly.boundary.distance(Point(x, y))
                            d_next = poly.boundary.distance(Point(px, py))
                            _near_approach = (d_now < BUFFER) and (d_next < d_now)
                        except Exception:
                            _near_approach = False
                    if (not inside_next) or (not inside_now) or _near_approach:
                        tgt = poly.representative_point()
                        c2 = bearing_to((x, y), (tgt.x, tgt.y))
                        verb = "移动" if atype == "move" else "飞行"
                        text = f"{unit} {verb} target_speed={sp:.1f} target_course={c2:.1f}"
                        self.area_rewrites += 1
                        if inside_now:
                            self.predicted_out_rewrites += 1
                        if inside_now and inside_next:
                            self.unnecessary_rewrites += 1
            out.append({"action_text": text, "action_type": atype})
        return out
