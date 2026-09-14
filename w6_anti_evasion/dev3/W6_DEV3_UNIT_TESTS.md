# W6-dev3 Unit Tests (T21–T26)

File: `test_w6_dev3_units.py` (top level). Result: **15/15 PASS** on 2026-09-04.
Regression: `test_w6_units.py` 34/34, `test_v5_units.py` 37/37, `test_v3_units.py` 49/49,
`test_v4_units.py` 41/41, `test_v6_audit_units.py` 49/49 — all green.

These are architecture-invariant tests for the WHO/WHAT/TARGET vs HOW boundary.

| Test | Assertion | Status |
|---|---|---|
| T21 no predictive waypoint | In dev3 (`EXECUTION_OVERRIDE=False`) no `_w6_intercept` waypoint is ever written; source write is guarded by the flag | PASS |
| T22 same assignment → same controller | W6 calls the same `USVController.step` from W5; no duplicate controller / standoff code in `anti_evasion` | PASS |
| T23 handoff only changes owner | `allocator_centric` changes assignment (`B` joins/leads `e`) and never touches track geometry | PASS |
| T24 screen does not move a platform | `ScreenPlan` is pure data (no action field); the only platform-move rewrite is guarded by `EXECUTION_OVERRIDE` | PASS |
| T25 legacy standoff preserved | standoff/approach/lock logic lives only in W5 `USVController` (`_standoff_move`, `LOCK_BAND`); no copy in the dev3 allocator | PASS |
| T26 execution equivalence | with no free USV and no handoff/reinforce, dev3 overlay returns exactly the base assignment ⇒ identical downstream execution | PASS |

Interpretation: the dev3 allocator cannot emit navigation; identical assignments reach the
identical legacy controller, so any behavioural delta of dev3 vs W5 is attributable to the
assignment policy only.
