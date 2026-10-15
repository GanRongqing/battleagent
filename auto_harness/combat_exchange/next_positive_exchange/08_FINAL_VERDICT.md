# 08 — FINAL VERDICT

## Candidate C10 = BUDGETED_COORDINATION (`white-combat-0010-v1`, parent ACE)
Reuses C7's 2-unit synchronized-lock package but caps **cumulative packages per episode at 3**.

## Did it achieve a positive exchange?
**NO.** Best hard case W2-6 = **0.688** (< 1.000). No scenario reached >1.000 beyond the existing
control W2-4 (which ACE already wins).

## Evidence-backed mechanism (reproducible)
- W2-6 own-lock units **55 → 75**; hostile-locked-never-own-lock **40 → 25**; ratio 0.556 → **0.688**
  (+24%), identical direction on all 5 seeds (11/16 vs 10/18).
- W2-4 wins retained 5/5 (C7 had regressed to 3/5) → the budget removed unnecessary coordination
  interference on a winning engagement.

## Round-1 candidate C9 (TASK_DEMAND_GATED_COORDINATION) — DROPPED
Hostile-lock demand gate formed **0 packages** (the helpful W2-6 packages occur before the owner is
hostile-locked) → behaviour identical to ACE → **NO_EFFECT** (H1 falsified).

## PROMOTE checklist (section 7)
| condition | status |
|---|---|
| Hard-group own-lock conversion improves | YES (W2-6 11→15) |
| Hard-group ratio improves | YES (0.556→0.688) |
| W2-4 no obvious control regression | YES (5/5 wins, -14%) |
| No passivity regression | YES (kills 50→55) |
| ACE assignment coverage intact | YES (free-owner-only diversion unchanged) |
| No strategy-ID specialisation | YES |
| No truth leakage | YES |
BUT the round objective (Target A: W2-6 > 1.000) was **NOT** reached.

## Verdict
**TARGETED_ONLY** — keep as an experimental hard-case (TARGETED) option: it delivers a reproducible
paired gain on W2-6 and does not break controls (strictly better than C7 on the control), but it does
not achieve a positive exchange and the gain is the C7 mechanism (the budget only removes C7's control
degradation). Not promoted to global DEFAULT.

confidence = MEDIUM.
