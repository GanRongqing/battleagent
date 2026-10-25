#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""agent_hybrid_coverage_bounds.py — C18: SENSOR_GEOMETRY_AWARE_SEARCH (area-bounded coverage).

Parent: C17 (agent_hybrid_uav_bounds.py). Candidate: white-combat-0018-v1.

Verified defect (E19): the base `CoverageMap` grid spans x∈[0,300 km], y∈[80,620 km]
(`COVERAGE_X0/X1`, `COVERAGE_Y0/Y1`), while the operational area is x∈[0,370.4], y∈[-277.8,277.8].
Consequences (VERIFIED from source constants + geometry):
  * `best_unobserved` can only propose cells at y>=80 km and may propose y up to 620 km — i.e. far
    outside the area. During GLOBAL_SEARCH this drives UAVs to the north boundary and out of the area
    (the E18 area-out deaths).
  * The entire southern half (y<80 km) and the eastern 70 km (x>300 km) are unrepresentable, so the
    search never plans them.

Mechanism (ONE, minimal): a coverage grid whose spatial extent matches the operational area
(x 0..370 km, y -280..+280 km) with the same cell size / weight / mark_covered semantics and the same
`best_unobserved`. No scenario/route/strategy ID, no truth, no black-state read. All other logic is C17.
"""
import sys

from agent_hybrid_uav_bounds import BoundedUAVAgentMain, BoundedUAVManager
from agent_hybrid_v5 import CoverageMap, COVERAGE_CELL

POLICY_ID = "white-combat-0018-v1"
PARENT = "C17(white-combat-0017-v1)"
MECHANISM = "SENSOR_GEOMETRY_AWARE_SEARCH"

# Operational-area-aligned bounds (global geometry constants, not scenario-specific).
AREA_X0, AREA_X1 = 0.0, 370_400.0
AREA_Y0, AREA_Y1 = -280_000.0, 280_000.0


class AreaCoverage(CoverageMap):
    """CoverageMap restricted to the operational area (fixes out-of-area / missing-south grid)."""

    def __init__(self):
        self.nx = max(1, int((AREA_X1 - AREA_X0) / COVERAGE_CELL))
        self.ny = max(1, int((AREA_Y1 - AREA_Y0) / COVERAGE_CELL))
        self.last_covered = {}
        self._weight = {}
        for ix in range(self.nx):
            x = AREA_X0 + (ix + 0.5) * COVERAGE_CELL
            w = 1.0 + 2.0 * max(0.0, 1.0 - min(x, 150_000.0) / 150_000.0)
            for iy in range(self.ny):
                self._weight[(ix, iy)] = w

    def _cell(self, x, y):
        ix = int((x - AREA_X0) / COVERAGE_CELL)
        iy = int((y - AREA_Y0) / COVERAGE_CELL)
        return (max(0, min(self.nx - 1, ix)), max(0, min(self.ny - 1, iy)))

    def _center(self, ix, iy):
        return (AREA_X0 + (ix + 0.5) * COVERAGE_CELL,
                AREA_Y0 + (iy + 0.5) * COVERAGE_CELL)

    def mark_covered(self, x, y, t, radius=65_000.0):
        c = self._cell(x, y)
        cells = [c]
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                nx, ny = c[0] + dx, c[1] + dy
                if 0 <= nx < self.nx and 0 <= ny < self.ny and (nx, ny) != c:
                    cells.append((nx, ny))
        for cc in cells:
            self.last_covered[cc] = max(self.last_covered.get(cc, -1e18), t)


class CoverageBoundsAgentMain(BoundedUAVAgentMain):
    def __init__(self, use_uavs=True, max_steps=40000):
        super().__init__(use_uavs=use_uavs, max_steps=max_steps)
        self.coverage = AreaCoverage()


if __name__ == "__main__":
    use_uavs = True
    for a in sys.argv[1:]:
        if a == "--no-uav":
            use_uavs = False
    CoverageBoundsAgentMain(use_uavs=use_uavs).run()
