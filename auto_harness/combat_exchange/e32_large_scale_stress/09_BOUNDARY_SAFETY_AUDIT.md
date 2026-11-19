# 09 — BOUNDARY SAFETY AUDIT (large scale)
| id | safety available | rewrites | predicted_out | preventive_buffer | current_out | unexpected | white USV OOB | white UAV OOB |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| L1 | true | 15 | 0 | 0 | 15 | 0 | 0 | 0 |
| L2 | true | 20 | 0 | 0 | 20 | 0 | 0 | 0 |
| L3 | true | 30 | 0 | 0 | 30 | 0 | 0 | 0 |
| L4 | true | 15 | 0 | 0 | 15 | 0 | 0 | 0 |
| L5 | true | 15 | 0 | 0 | 15 | 0 | 0 | 0 |
Public polygon loaded on every run (`available=true`), no fallback to W2 box. Engine AREA_TRACE shows only Black
removals; **White USV/UAV AREA_OUT = 0 in all runs**. `unexpected_rewrites = 0`. Rewrites are `current_out`
(boundary recovery for forward UAVs), consistent with the tether reaching the octagon edge.
