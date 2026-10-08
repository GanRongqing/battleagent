# 16 — COVERAGE REGRESSION CHECK
C7 only ever diverts a **free** (no-target) USV; it never reassigns an owner of another target. Therefore
it **cannot** turn a known/actionable target from ≥1 owner to 0 owners — the coverage-floor invariant
(step 15) holds **by construction**.
Exact Assignment-Coverage / zero-owner-actionable-target counts are **NOT_MEASURED** (assignment state is
not emitted in the frozen game logs / agent stdout).
Verdict: **coverage regression = NO** (by construction).
