# 01 — BASELINE INTEGRITY AUDIT (E35 P0)
Re-read E33 (`e33_new_16_scenarios`) and E34 (`e34_fair_opponent_16`). Corrections / comparability:
1. **E33 Black has NO UAV** (VERIFIED by building N01 in-process: 30 ships, 0 planes). The "Black UAV advantage"
   explanation is invalid; both sides are ship-only in all 16 scenarios.
2. **E33→E34 changed TWO White factors at once**: White USV count (10/15/20/30 → 30/20/24/45) AND White USV
   radar (20→30 km). The pooled CER gain (0.651→1.251) therefore **cannot be attributed to a single factor** —
   this is exactly why the 2×2 ablation (A/B/C/D) is required.
3. **White count change is confounded with deployment geometry**: horizontal_N spacing depends on N (20 km ≤20,
   18 km for 24/30, 12 km for 45). So "count" includes a formation/spacing change; a pure-count effect would
   require holding deployment fixed (noted, not fully separable here).
4. **F03 (E33 30/0 → E34 22/23)** must not be called "geometry luck" without isolation — it is a confounded
   count+radar+deployment change; the 2×2 separates radar (B) from count/deployment (C).
5. **Corrected grouped pooled CER (E34)** (old fig3 values were wrong):
   - 20v20 (F08,09,10,11,14,15): K=88, L=60 → **1.467** (was mis-stated 1.52)
   - 24v24 (F12,F16): K=46, L=33 → **1.394** (was 1.33)
   - 30v30 (F01–07): K=164, L=160 → **1.025** (was 1.06)
   - 45v45 (F13): 45/21 → **2.143**
   Total 343/274 = 1.251 (matches).
Comparability: A=E33 and D=E34 are already-valid runs with identical engine hash `a509457250bc2799`, same
Policy (C31), same Black routes; B and C are run fresh here under the same conditions.
