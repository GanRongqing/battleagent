# 01 — KC-F1 Metric Audit

## Original definition (from w5_failure_audit.py)
- `detected` = unique target names from agent-log `[DETECT]` events (per episode).
- `killed` = unique target names from `[KILL]`.
- `committed` = unique target names appearing in `[ASSIGN]` (proxy).
- KC-F1 = `detected - killed - committed` (set difference), counted once per (target, episode).

## Numerator / denominator
- numerator: 250 (unique detected-but-never-committed-and-not-killed targets, across 24 episodes).
- denominator: 295 (unique detected-but-not-killed targets).
- rate: 84.7%.

## Is it a repeated per-step count? NO
A target that is uncommitted for 100 steps contributes **1** (not 100), because the sets are unique
per episode. So **84.7% cannot be read as "84.7% of all target-step observations are uncommitted."**
It reads as: "of the unique targets that were detected but not killed, 84.7% never appeared in the
`[ASSIGN]` proxy at all."

## Caveats
1. `committed` uses the step-level `[ASSIGN]` PROXY, which is NOT canonical owner mapping (it
   over-counts: assign_rate > 100% on S1/S2/S6). A target with no `[ASSIGN]` is reliably "never
   committed" (lower bound); a target WITH `[ASSIGN]` may or may not be canonically committed.
2. `detected` uses `[DETECT]` events, which may under-count (a target can be observed but not emit a
   fresh `[DETECT]`). So the "never committed" fraction is a LOWER bound on true under-commitment.
3. The metric is per-episode; a target counted in 4 seeds contributes up to 4 times (once per seed).

## Two required statistics (established in this audit)
- STEP-LEVEL: per decision step, count current detected/tracked targets with no canonical commitment.
- TARGET-EPISODE LEVEL: per (target, episode), was it ever committed? (this is what 84.7% is).

This audit reports BOTH.
