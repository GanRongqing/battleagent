# 09 — E31 / E32 / E33 COMPARISON (kept separate; NOT merged)
| batch | scope | result |
|---|---|---|
| E31 | 13 original scenarios (W2 routes + scale, **White has UAVs**) | 13/13 CER>1, pooled 2.727, USV/UAV OOB=0 |
| E32 | 5 scale configs + 2 seed re-checks (**White has UAVs**) | 7/7 CER>1, USV/UAV OOB=0 |
| E33 | 16 new route scenarios (**White USV-only, 0 UAVs, 30 Black with 30km radar**) | **3/16 CER>1, pooled 95/146=0.651, 2/16 Victory, OOB=0** |
E33 scenarios are distinct configurations (new opponent routes; White without UAVs). They are NOT merged with
E31/E32. The comparison shows C31's advantage depends on **UAV recon and numerical parity**; when both are
removed, C31 loses — the identified generalization boundary.
