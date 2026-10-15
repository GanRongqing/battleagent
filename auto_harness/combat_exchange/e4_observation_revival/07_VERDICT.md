# 07 — VERDICT

## Mechanism (W2-6, seed 43001)
| | own-lock units | sustained windows | max concurrency | prelock deaths | K/L | ratio |
|---|---|---|---|---|---|---|
| ACE OFF | 11 | 16 | 4 | 8 | 10/18 | 0.556 |
| ACE ON | **14** | **26** | **6** | 6 | **14/20** | **0.700** |
| C10/C11 ON | 14 | 26 | 6 | 6 | 14/20 | 0.700 |
REVIVE restores mis-killed live contacts -> **+63% sustained windows, max concurrency 4->6, kills 10->14**.
Under REVIVE, ACE == C10 == C11 on W2-6 (the revive dominates; the coordination mechanisms become moot).

## Control
W2-4 collapses: ACE 2.000 -> **0.450** (12/6 -> 9/20). W2-2 flat. W2-1 unchanged (still 0 kills).

## Interpretation
`killed_names` was **load-bearing**: the same legal `obs.active` that contains mis-killed LIVE enemies also
appears to retain some truly-dead/stale contacts, so a blanket "active ⇒ alive" revive reintroduces ghosts,
causing over-engagement and heavy losses on a scenario the agent used to win. The suppression heuristic
trades false-kills (hurting W2-6) against ghost targets (protecting W2-4).

## Verdict
**CONTROL_REGRESSION / NOT PROMOTABLE as a global change (close to REJECT).**
- W2-6 improved materially but did **not** exceed 1.000 (0.700 < 1.0).
- W2-4 (positive control) severely regressed.
- No `PROMISING_DETERMINISTIC_RESULT` (that required >1 with no control regression).
- The fix must NOT be enabled globally. Keep it disabled by default.

## New failure stage / next real question
The naive revive is not the answer; a **dead-vs-alive discriminator** is needed (e.g., require the revived
contact to actually MOVE / be re-classified, rather than revive on any radar hit). That is the genuine next
mechanism question — not another coordination candidate. Not implemented this round.
