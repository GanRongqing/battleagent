# 08 — Open Issues & Next Steps

Status legend: OPEN / IN PROGRESS / PAUSED / BLOCKED / DONE.

## A. White anti-leak candidate (white-auto-0001-v1)
| # | item | status | detail | source |
|---|---|---|---|---|
| A1 | DEV paired performance (8001–8030) | DONE | W5 30/30, candidate 30/30; verdict SUPPORTED (provisional); brk 0.467→0.200 (11:3), defeat 0.133→0.200 (n.s.) | `auto_harness/phase1/WHITE_PHASE1_FINAL_REPORT.md` |
| A2 | Mechanism KPIs (unblocked HIGH/CRITICAL duration, triggers, preemptions) | IN PROGRESS | only available after full DEV; runtime audit now env-gated via `W8_AUDIT_LOG` | `run_white_phase1.py`, `agent_hybrid_w8_containment.py` |
| A3 | Fresh validation 8101–8130 | DONE (FAIL) | DEV improvement did not reproduce; breakthrough direction reversed (0.233→0.367); no promotion | `auto_harness/phase1/WHITE_HARNESS_PHASE1_FINAL_REPORT.md` |
| A4 | Cross-opponent 8201–8210 (E0/E1/E2/E3) | OPEN (gated) | representative E1 to be chosen (B1 or B2) | this pack |
| A5 | Candidate promotion (`active`) | CLOSED (NOT promoted) | Fresh FAIL; white-auto-0001-v1 remains candidate/validation; W5 frozen current |
| A6 | ARTIFACT re-registration | DONE | artifact updated after adding runtime audit; bundle `2fcde232ba81…` | `auto_harness/phase1/ANTI_LEAK_ARTIFACT.json` |

## B. Black taxonomy / B0-v2
| # | item | status | detail | source |
|---|---|---|---|---|
| B1 | E1 B1-vs-B2 redundancy | OPEN | INCONCLUSIVE (behavior distance 0.371) | `POLICY_DIFFERENCE_MATRIX_V2.csv` |
| B2 | AUTO1 response trigger | OPEN | fired 0/10; timeout fallback only; a v2 would be needed | `.../calibration_s2/traces/*_autoevents.json` |
| B3 | B0-v2 status | DONE (validation) | speed axis non-degenerate; E0 retained | `b0_v2/` |
| B4 | B0-v2 seed 9056 speed outlier | OPEN (minor) | trace-sampling artifact (50% zero-delta samples) | `b0_v2/n90_review/` |
| B5 | B0-v1 alias | OPEN | alias still points to v1; decision to move to v2 not made | this pack |

## C. Instrumentation / data gaps
| # | item | status | detail |
|---|---|---|---|
| C1 | White USV coordinates in historical logs | NOT RECORDED | W5 logs print counts + enemy TOP only; fixed only for the 10-episode two-sided replay set |
| C2 | Black ground-truth geometry | NOT RECORDED | sidecars record radar-visible subset only (proxy) |
| C3 | requested_n fields in historical CSVs | NOT FOUND | most summaries store only valid_n |
| C4 | `bt_regression_eval` consolidated summary | NOT FOUND | use per-file CSVs in `bt_regression_eval/` |

## D. Next steps (recommended order)
1. Resume White Phase1 DEV candidate (12 episodes) → run `analyze_phase1.py` → causal verdict.
2. If SUPPORTED: run fresh 8101–8130 (paired, no tuning), then cross-opponent 8201–8210.
3. Decide `white-auto-0001-v1` status (validation / active) per gate results.
4. Optionally generate two-sided replay sets for B3 and the candidate (containment blocker geometry).
5. Resolve E1 (B1/B2) redundancy if a new E1 representative is needed.
6. Consider `black-auto-0001-v2` if the legal response trigger is required empirically.

## E. Things explicitly NOT changed this round
White policy, Black policy, simulator, strategy behavior, controller, BT, physics, evaluation logic.
Only documentation + master tables were added (`docs/team_sync/`).
