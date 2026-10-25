# 04 — COVERAGE MODEL AUDIT
- Scenario UAV radar: `radar_distance=60000`, `radar_sector=[-30,30]` (forward 60° sector).
- `CoverageMap.mark_covered(x,y,now)` marks the platform's cell and neighbours **without heading/sector**,
  i.e. it treats a passing platform as having scanned in all directions.
=> Coverage estimate is **optimistic vs a forward-sector sensor**. VERIFIED (source geometry mismatch).
- Impact on W2-1 scheduling: **INFERRED/not binding** — C17 kept all 10 UAVs alive ~2× longer yet still
  produced 0 own-lock / 0 kills, so coverage-estimate error alone is not the W2-1 bottleneck this round.
  (No code change to CoverageMap this round.)
