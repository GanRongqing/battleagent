# 01 — ORIGINAL SCENARIO AUDIT (E34 P0)
Source zip `/root/autodl-tmp/test/敌方策略-16种路线.zip` (untouched). **Audited from the actual scenario files
(VERIFIED by building each scenario in-process and counting units):**
| 场景 | 黑方USV(路线usvNum) | 黑方UAV | 白方USV(E33原始) | 白方UAV |
|---|---:|---:|---:|---:|
| N01–N07 | 30 | **0** | 10 | 0 |
| N08–N11 | 20 | **0** | 15/20/20/20 | 0 |
| N12 | 24 | **0** | 15 | 0 |
| N13 | 45 | **0** | 10 | 0 |
| N14–N15 | 20 | **0** | 20 | 0 |
| N16 | 24 | **0** | 20 | 0 |
**Key correction:** the scenario files define **NO Black UAVs** — the E34 brief's "Black UAV = USV count" column is NOT
present in the configs (Black is ships-only; `black_plane_alive_num` is fixed 0 in the original code). Per
"以实际场景配置文件为准" and "黑方数量不变", the file-grounded parity is: White USV = Black USV, **White UAV = 0 =
Black UAV**, White USV radar 20 km → 30 km (= Black). Black routes/waypoints/speeds/counts are unchanged.
