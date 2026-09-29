# 00 — Strategy Registry Audit (STOP: registry != 15)

## STOP reason
The phase premise is **B0-B3 (4) + Wave1 (5) + Wave2 (6) = 15** enemy strategies. The actual
project registry does **not** contain a 5-strategy "Wave1" or 6-strategy "Wave2" set. Per the
phase rules ("if registry != 15 STOP; do not add/remove"), evaluation was **not started**.

## What actually exists (enumerated, not guessed)

### GROUP OLD — confirmed (4)
| group | short_id | actual registered name | source file | scenario/route id |
|-------|----------|------------------------|-------------|-------------------|
| OLD | B0 | B0_RANDOM | `opponent_profiles.py` (B0) / `strategy_library` black-b0 | `scenario_builder random_waypoint` |
| OLD | B1 | B1_MULTI_AXIS | `opponent_profiles.py` (B1) | `opponent_profiles.spatial_groups` |
| OLD | B2 | B2_COORDINATED_PRESSURE | `opponent_profiles.py` (B2) | `_coordinated_pressure_paths` |
| OLD | B3 | B3_ADAPTIVE | `opponent_profiles.py` (B3) | runtime legal replan |
(also B4_DOCTRINE_MIX exists but is a seed-driven mix of B1/B2/B3, not a distinct Wave member.)

### External (xiaowang / 师弟) — confirmed, but only **2**, not 5+6
| group | short_id | actual registered name | source file | scenario |
|-------|----------|------------------------|-------------|----------|
| EXTERNAL | D | black-external-dispersed-v1 | `external_dispersed.py` (from `分散式.py`) | `测试1-黑方艇分散式前进.json` |
| EXTERNAL | T | black-external-twowave-v1 | `external_twowave.py` (from `两波次.py`) | `测试2-黑方艇两波次前进.json` |
Source archive `wang.rar` (sha256 4518...) contains exactly these 2 scripts + 2 JSONs.
`xiaowang_source/sces.json` registers only `地毯式前进` and `两波次前进`.

### Other registries (for completeness)
- `hsystem/simserver/config/sces.json`: 6 White-facing `sim_script/scenario/plan/*` strategies
  (these are W5's own six_strategy set, not enemy waves) + 9 non-strategy scenario entries.
- `strategy_library/strategy_library.db` `strategies`: white-w5, white-w6, white-w7, black-b0,
  black-b1, black-b2, black-b3.
- `policy_system/cards/`: black-b0-v1, b1-v1, b2-v1, b3-v1.
- `opponent_b0_v2.py` / `b0_v2/`: a B0 v2 refinement (single strategy).
- No file/registry anywhere defines a "Wave1" (5) or "Wave2" (6) strategy set.

## Conclusion
- Registry count = **4 (B0-B3) + 2 (external)** distinguishable enemy strategies, plus White plan
  strategies — **not 15**.
- STOP condition 1 (registry != 15) and 2 (cannot confirm Wave1/Wave2 identity) both triggered.
- No evaluation was run; ACE and all enemy strategies unmodified.
