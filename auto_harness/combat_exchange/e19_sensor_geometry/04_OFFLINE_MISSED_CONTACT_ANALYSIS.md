# 04 — OFFLINE MISSED-CONTACT ANALYSIS (diagnosis only; truth never fed online)
Method: replay C17 W2-1 UAV trajectory (legal course/pos) offline; reconstruct Black positions from
`路线1-*.json` waypoints+speed; evaluate UAV forward ±30°/60km geometry each step.
Results (C17 W2-1):
- **min UAV→any-Black distance = 57.3 km** (only at 01:53).
- Unit-steps with any Black ≤60 km = **4**; inside ±30° sector = **4**; outside sector = **0**.
- Actual active-Black steps in the log = **2** (same instant) → consistent.
Classification: **GEOMETRY_MISS / INSUFFICIENT_OPPORTUNITY** (targets almost never inside the UAV
envelope; no SECTOR_MISS, no SENSOR_OR_OBSERVATION_GAP evidence, no FALSE_COVERAGE-caused contact loss
demonstrable). Route reconstruction is approximate → **INFERRED** for the exact 57.3 km figure; the
observation side (2 active steps) is **VERIFIED**.
