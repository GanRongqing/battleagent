# 09 — E8.1 FINAL REPORT
- Repaired two runner-isolation defects (shared `temp.py` symlink; fixed-port stale-engine reuse).
- The four E8.1 runs still collapsed into two identical scenario pairs → **runtime scenario identity is
  not proven** (Defect 3: `temp.py` != executed scenario).
- Consequently all E8.1 results are INVALID; E7 results are re-classified PLAUSIBLE_UNVERIFIED.
- Verdict: **EVALUATION_BLOCKED**. No version promotion; defaults unchanged; C10 INCONCLUSIVE.
- Next: add engine-level scenario identity evidence and re-run a minimal 4-way panel, then fresh-RNG.
