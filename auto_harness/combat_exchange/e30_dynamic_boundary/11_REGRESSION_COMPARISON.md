# 11 — REGRESSION COMPARISON (C30 → C31)
| group | C10 | C30 | **C31** |
|---|---|---|---|
| W2 pooled CER | 0.725 | 1.922 | **1.922** (identical) |
| W2 positive scenarios | 4/6 | 6/6 | **6/6** |
| non-W2 pooled CER | 8.000 | 0.844 | **13.000** |
| non-W2 positive scenarios | 7/7 | 3/7 | **7/7** |
| 13/13 CER>1 | no | no | **YES** |
| USV AREA_OUT | 0 | 0 | **0** |
| UAV AREA_OUT | 0 | 0 | 35 (no buffer) → **0** (buffer, W2-1+S10 verified) |
Root cause fixed: the safety now uses the real public polygon; the scale fleet (y≈375–435km) is correctly inside
the scale octagon, so it is no longer dragged to (185,0). W2 is unchanged (its real area equals the old box).
