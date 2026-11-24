# 01 — SCENARIO INVENTORY (E33)
Source: `/root/autodl-tmp/test/敌方策略-16种路线.zip` (single archive; originals untouched; extracted to /tmp for
inspection). **16 valid independent scenarios**: `横向编队-路线01..16`, each = one plan + one route JSON
(`路线NN-<战术名>.json`), all on the same map `台岛东南部海域.json` (x0..370.4km, y±277.8km).
Common: **Black = 30 USV** (route-based waypoints, speed 6 m/s, radar 30km); **White = N USV, 0 UAV**
(formation_mode `horizontal_N`, N∈{10,15,20,30}); ship radar 20km; end_time 600000, ratio 100.
Deterministic (route-based; no random process; seed does not change paths).
Groups: N01–07,N13 = horizontal_10 (10 USV); N09,11,12 = horizontal_15; N08,14,15,16 = horizontal_20; N10 = horizontal_30.
The novelty is the **opponent route tactics** (16 distinct maneuvers), not the map. No UAVs for White.
Full per-file SHA256/route/formation in `02_SCENARIO_CONFIGS.csv`.
