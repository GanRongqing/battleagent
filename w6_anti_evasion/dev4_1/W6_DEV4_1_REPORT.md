# W6-dev4.1 Free-to-Imminent Trigger Relaxation

## 1. Motivation
Dev4 quality is mostly GOOD (5/7) but live expressivity was narrow (trigger only on
uncovered/deficit). dev4.1 widens FREE->imminent eligibility under a conservative candidate
gate: ETA(P,C) <= 1.5 x current best-lead ETA(C), below emergency concentration (per-target,
scale-agnostic), FREE-only.

## 2. Single change (only WHO/TARGET/TASK)
FREE platform -> imminent (risk>=HIGH) corridor with ETA<=1.5x lead and conc<cap.

## 3. Frozen components
SOFT/HARD classes, reserve, handoff, weights, hysteresis, cooldown, controller/HOW untouched;
execution override = 0 (see W6_DEV4_1_DIFF_AUDIT.md).

## 4. Offline replay (2035 saved states)
- states with an imminent corridor: 895; with a FREE platform: 745.
- Under the 1.5x-ratio rule, fired states: **0/2035** (dev4 original ~62/2035 = 3.1%).
Reason: FREE platforms are generally far from imminent corridors whose owners already hold a
short best-lead ETA, so ETA(free)/ref > 1.5 almost always. The late-game FREE adds that dev4
did make were uncovered-urgent with ratios ~1.5 (e.g. 15.8k/10.4k) — borderline, and mostly
GOOD (5/7).

## 5. Decision expressivity
dev4.1 as specced adds ~0 new assignment changes offline -> eligibility is STILL too narrow;
the 1.5x candidate gate blocks the very opportunity the audit identified (extra FREE attacker
on imminent corridors, which live proved mostly GOOD even when not strictly "uncovered").

## 6. Safety / commitment invariants
T37-T46 pass (10/10); regression suites green. No SOFT/HARD change; no controller change.

## 7. Live sanity
NOT RUN: offline acceptance gate requires new-trigger firing > dev4, which is 0/2035. Per the
round's gate, do not run live on a no-effect trigger.

## 8. Event quality
N/A (no new events offline). Note: dev4's uncovered-urgent FREE adds were 5 GOOD / 2 BAD
(both very-late, harmless).

## 9. Decision
**STOP — TRIGGER RELAXATION (1.5x) NOT EFFECTIVE as specified.** The 1.5x ratio gate is too
conservative given FREE platforms' geometry. The evidence (dev4's mostly-GOOD uncovered-urgent
adds) suggests imminent-corridor reinforcement is valuable even when the extra attacker is not
within 1.5x of the current lead. Recommended next change (NOT this round): evaluate a
coverage-safe imminent reinforcement with a weaker/derived gate (e.g. only when the corridor is
under-concentrated relative to emergency cap and no coverage loss), or derive the ratio
threshold from the observed dev4 event ratios rather than a fixed 1.5.
