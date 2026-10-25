# 02 — SENSOR FOOTPRINT AUDIT (read-only)
Source facts (VERIFIED):
- UAV radar: distance 60 km, sector **[-30°, +30°] forward** (`RED_FORCE_CONFIG[uav]`).
- USV radar: ~20–35 km, **omnidirectional**.
- `CoverageMap.mark_covered(x,y,t)` marks the platform cell + **3x3 neighbours (30 km cells)** with **no
  heading/sector** — i.e. it books a full-disc scan for a forward-sector sensor.
- `CoverageMap` grid bounds: `COVERAGE_X0/X1=0..300 km`, `COVERAGE_Y0/Y1=80..620 km`.
- Operational area: x 0..370.4 km, y **-277.8..+277.8 km**.

=> Two VERIFIED coverage-geometry defects:
1. **Sector ≠ disc**: direction-agnostic marking.
2. **Grid ≠ area**: only y∈[80,620] km is representable (southern half missing; cells up to 620 km
   outside the area), and x∈[0,300] km (eastern 70 km missing).
UAV heading used = real legal `course` from `/status` (not planned course). Radar状态 not exposed by
observation → UNKNOWN where applicable; we do not assume a scan we cannot see.
