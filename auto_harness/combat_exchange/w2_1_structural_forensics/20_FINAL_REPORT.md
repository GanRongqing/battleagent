# 20 — W2-1 Structural Failure Forensics — Final Report

0 replay episodes (existing frozen logs sufficient for the timeline). ACE unchanged; truth offline only.

1. 6270 vs 27270 = pooling artifact (all-30 median vs W2-1 outlier). Not an offset.
2. First White death: at T_ABS 27,270 s, in a sudden collapse (20 deaths in ~2,700 s).
3. Attacker: not attributable per-unit from frozen logs (killer id NOT_MEASURED); the White had stale
   (lost) tracks of Black units, not live contacts.
4. Did White know the attacker? PARTIAL — stale/lost tracks exist (lost=4 at t=6870; lost=5–7 during
   the early deaths); no fresh track at death.
5. Chance to lock/fire? NO own lock/hit recorded before death (vis=0 through the first 12 deaths).
6. First actionable warning ≈ 6,870 s; ~20,400 s before the first death; but with no maintainable lock.
7. 20 deaths: dominant OBSERVED_NOT_ENGAGEABLE (with UNOBSERVED component); no per-unit killer proof.
8. Collapse type: SUDDEN_COLLAPSE.
9. Sensor/weapon asymmetry: NOT_MEASURED (weapon/lock envelope not reconstructed from source here).
10. Long NO_OP / wrong movement? NOT directly measured, but vis=0+lost>0 => the units moved without a
    maintainable lock (track-maintenance failure, not idle).
11. Assigned target vs killer mismatch: NOT_MEASURED (no per-unit assignment/killer join in frozen logs).
12. Local force disadvantage at death: NOT_MEASURED (truth join not done).
13. C6B trigger = NO (0 admissions).
14. Stage-A signal mismatch: own-geometry cohesion did not match the real failure (track->lock
    conversion), hence NO_TRIGGER.
16. W2-2 did: acquire a **live** contact at ~6,270 s, hold it, convert to lock/hit, survive.
17. Earliest actionable divergence: SENSING_VISIBILITY / ENGAGEMENT_RANGE (stale-track / cannot-lock).
18. Next mechanism (concept only): track-maintenance / early-warning at engagement range.

## Verdict
Dominant = **OBSERVED_NOT_ENGAGEABLE**; collapse = **SUDDEN_COLLAPSE**; C6B = **NO_TRIGGER** (DROP).
confidence = MEDIUM. No candidate implemented. No ACE change. Truth offline only.
