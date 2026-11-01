#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""universal_safety.py — E25 Universal Boundary Safety (post-ActionSafety, all USV actions).

Every USV `move` action (from _move, _standoff_move, patrol, press, chase, skill handoff, …) is checked by
predicting the next control-period position; if it would leave the operational area, the course is replaced
with a legal recovery course toward the area centre. Applies AFTER ActionSafety.filter, before /apply, so no
movement path can bypass it. Never touches lock actions or UAV commands; no physics/radar/rule changes.
Area geometry is a public constraint (x 0..370.4 km, y ±277.8 km) with a safety margin.
"""
import math
import re

from agent_hybrid_v5 import ActionSafety, USV_SPEED, bearing_to

AREA_XMIN, AREA_XMAX = 0.0, 370_400.0
AREA_YMIN, AREA_YMAX = -277_800.0, 277_800.0
MARGIN = 8_000.0
DT = 31.0
CENTER = ((AREA_XMIN + AREA_XMAX) / 2.0, 0.0)

_SRE = re.compile(r"target_speed=([-\d.]+)")
_CRE = re.compile(r"target_course=([-\d.]+)")


def _parse(text):
    m1 = _SRE.search(text)
    m2 = _CRE.search(text)
    return (float(m1.group(1)) if m1 else None, float(m2.group(1)) if m2 else None)


def _inside(x, y, m=MARGIN):
    return (AREA_XMIN + m) <= x <= (AREA_XMAX - m) and (AREA_YMIN + m) <= y <= (AREA_YMAX - m)


def _predict(x, y, sp, crs, dt=DT):
    r = math.radians(crs)
    return x + sp * dt * math.sin(r), y + sp * dt * math.cos(r)


class BoundaryAwareSafety(ActionSafety):
    """ActionSafety + universal USV area protection."""

    def __init__(self):
        super().__init__()
        self.area_rewrites = 0

    def filter(self, actions, obs, legal):
        safe = super().filter(actions, obs, legal)
        usv = {u["name"]: u for u in obs.usvs
               if u.get("is_alive") and u.get("position")}
        uav = {u["name"]: u for u in obs.uavs
               if u.get("is_alive") and u.get("position")}
        out = []
        for a in safe:
            text = a["action_text"]
            atype = a["action_type"]
            unit = text.split(" ", 1)[0] if text else None
            if atype == "move" and unit in usv:
                sp, crs = _parse(text)
                if sp is not None and crs is not None:
                    x, y = usv[unit]["position"][0], usv[unit]["position"][1]
                    px, py = _predict(x, y, sp, crs)
                    if not _inside(px, py) or not _inside(x, y):
                        c2 = bearing_to((x, y), CENTER)
                        text = f"{unit} 移动 target_speed={USV_SPEED:.1f} target_course={c2:.1f}"
                        self.area_rewrites += 1
            elif atype == "fly" and unit in uav:
                sp, crs = _parse(text)
                if sp is not None and crs is not None:
                    x, y = uav[unit]["position"][0], uav[unit]["position"][1]
                    px, py = _predict(x, y, sp, crs)
                    if not _inside(px, py) or not _inside(x, y):
                        c2 = bearing_to((x, y), CENTER)
                        text = f"{unit} 飞行 target_speed={sp:.1f} target_course={c2:.1f}"
                        self.area_rewrites += 1
            out.append({"action_text": text, "action_type": atype})
        return out
