# 01 — BOUNDARY SOURCE AUDIT
- Judge uses a real shapely Polygon: `judge_system.set_area(points)` → `self.area = Polygon(points)`; units outside are killed.
- Builders set it per scenario: W2 (`adaptation.build_simulation`) uses `area/台岛东南部海域.json`;
  scale (`scenario_builder`) uses `Demo/任务区域.json`; external_* use their own engines.
- `/status` did NOT expose the area; the old safety used a hardcoded W2 rectangle (the E29 bug).
- Area is **public map geometry** (rendered as "Area"), identical format across scenarios; not enemy truth.
Answers: area is an arbitrary polygon (W2 is a 4-vertex rectangle; scale is an 8-vertex octagon); both are public
map info; the API did not expose it (now added as a public field); it is fixed per Episode; old safety ≠ real area.
