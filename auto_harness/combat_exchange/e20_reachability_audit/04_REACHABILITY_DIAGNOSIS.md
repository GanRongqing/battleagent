# 04 — REACHABILITY DIAGNOSIS
Observed (VERIFIED): min White-USV → positioned-Black distance over the whole episode:
| scenario | min distance | K/L |
|---|---:|---|
| **W2-1** | **123.4 km** | 0/20 |
| W2-4 | 2.1 km | 12/7 |
| W2-3 | 3.0 km | 12/15 |
| W2-5 | 0.1 km | 27/14 |
| W2-6 | 2.8 km | 11/16 |
In W2-1 the fleet never closes to engagement range; the only positioned contact (60 s) came from a UAV
at ~57 km and was >123 km from every White USV → no legal weapon/lock opportunity. All other scenarios
close to 0.1–3.0 km and engage.
Classification: **OUT_OF_SENSOR_RANGE / reachability**, driven by scenario geometry (Black arrow
breakthrough) and White's defensive screen — **not** a sector miss, sensor-state fault, or observation
pipeline failure. Bearing-only `被动告警` tracks (up to 15) never carry range, so they cannot enable locks.
